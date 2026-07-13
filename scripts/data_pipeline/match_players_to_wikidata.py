#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

AUTO_MATCH_SCORE = 85
AUTO_MATCH_MARGIN = 20
DEFAULT_DELAY = 1.0
DEFAULT_MAXLAG = 5
DEFAULT_MAX_RETRIES = 6
DEFAULT_FACT_BATCH_SIZE = 25
CACHE_SAVE_EVERY = 25

TEAM_ALIASES = {
    "Algeria": ["Algeria"],
    "Argentina": ["Argentina"],
    "Australia": ["Australia"],
    "Austria": ["Austria"],
    "Belgium": ["Belgium"],
    "Bosnia-Herzegovina": ["Bosnia and Herzegovina", "Bosnia-Herzegovina", "Bosnia"],
    "Brazil": ["Brazil"],
    "Canada": ["Canada"],
    "Cape Verde": ["Cape Verde", "Cabo Verde"],
    "Colombia": ["Colombia"],
    "Congo DR": ["DR Congo", "Congo DR", "Democratic Republic of the Congo"],
    "Croatia": ["Croatia"],
    "Curacao": ["Curaçao", "Curacao"],
    "Czechia": ["Czechia", "Czech Republic"],
    "Ecuador": ["Ecuador"],
    "Egypt": ["Egypt"],
    "England": ["England", "United Kingdom"],
    "France": ["France"],
    "Germany": ["Germany"],
    "Ghana": ["Ghana"],
    "Haiti": ["Haiti"],
    "Iran": ["Iran"],
    "Iraq": ["Iraq"],
    "Ivory Coast": ["Ivory Coast", "Côte d'Ivoire", "Cote d'Ivoire"],
    "Japan": ["Japan"],
    "Jordan": ["Jordan"],
    "Mexico": ["Mexico"],
    "Morocco": ["Morocco"],
    "Netherlands": ["Netherlands", "Holland"],
    "New Zealand": ["New Zealand"],
    "Norway": ["Norway"],
    "Panama": ["Panama"],
    "Paraguay": ["Paraguay"],
    "Portugal": ["Portugal"],
    "Qatar": ["Qatar"],
    "Saudi Arabia": ["Saudi Arabia"],
    "Scotland": ["Scotland", "United Kingdom"],
    "Senegal": ["Senegal"],
    "South Africa": ["South Africa"],
    "South Korea": ["South Korea", "Korea Republic", "Republic of Korea"],
    "Spain": ["Spain"],
    "Sweden": ["Sweden"],
    "Switzerland": ["Switzerland"],
    "Tunisia": ["Tunisia"],
    "Türkiye": ["Türkiye", "Turkey"],
    "United States": ["United States", "United States of America", "USA", "U.S."],
    "Uruguay": ["Uruguay"],
    "Uzbekistan": ["Uzbekistan"],
}


def clean(value: str) -> str:
    if pd.isna(value):
        return ""
    value = str(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ascii_fold(value: str) -> str:
    value = clean(value)
    value = unicodedata.normalize("NFKD", value)
    return value.encode("ascii", "ignore").decode("ascii")


def norm_text(value: str) -> str:
    value = ascii_fold(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def hash8(*parts: str) -> str:
    joined = "||".join(norm_text(str(part)) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8]


def wikidata_url(qid: str) -> str:
    return f"https://www.wikidata.org/wiki/{qid}"


def image_title_from_url(url: str) -> str:
    if not url:
        return ""
    filename = unquote(url.rstrip("/").split("/")[-1])
    filename = filename.replace("_", " ")
    return f"File:{filename}" if filename else ""


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def backoff_delay(attempt: int, base_delay: float, retry_after: str | None = None) -> float:
    parsed_retry_after = parse_retry_after(retry_after)
    if parsed_retry_after is not None:
        return max(base_delay, parsed_retry_after)
    return max(5.0, base_delay * (2 ** (attempt - 1)))


def request_json(
    session: requests.Session,
    url: str,
    params: dict[str, str | int],
    *,
    timeout: int,
    delay: float,
    max_retries: int,
    request_label: str,
    accept: str = "application/json",
) -> dict:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url,
                params=params,
                timeout=timeout,
                headers={"Accept": accept},
            )

            if response.status_code in {429, 503, 504}:
                wait_seconds = backoff_delay(attempt, delay, response.headers.get("Retry-After"))
                if attempt == max_retries:
                    response.raise_for_status()

                print(
                    f"[retry] {request_label} returned HTTP {response.status_code}; "
                    f"sleeping {wait_seconds:.1f}s before retry {attempt}/{max_retries}."
                )
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            data = response.json()

            error = data.get("error", {}) if isinstance(data, dict) else {}
            error_code = clean(error.get("code", ""))
            if error_code in {"maxlag", "ratelimited"}:
                wait_seconds = backoff_delay(attempt, delay, response.headers.get("Retry-After"))
                if attempt == max_retries:
                    error_info = clean(error.get("info", ""))
                    raise RuntimeError(
                        f"{request_label} failed after {max_retries} attempts: "
                        f"{error_code} {error_info}".strip()
                    )

                print(
                    f"[retry] {request_label} returned API error {error_code}; "
                    f"sleeping {wait_seconds:.1f}s before retry {attempt}/{max_retries}."
                )
                time.sleep(wait_seconds)
                continue

            time.sleep(delay)
            return data

        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt == max_retries:
                raise

            wait_seconds = backoff_delay(attempt, delay)
            print(
                f"[retry] {request_label} failed with {exc.__class__.__name__}; "
                f"sleeping {wait_seconds:.1f}s before retry {attempt}/{max_retries}."
            )
            time.sleep(wait_seconds)
        except ValueError as exc:
            last_error = exc
            if attempt == max_retries:
                raise RuntimeError(
                    f"{request_label} returned a non-JSON response after {max_retries} attempts."
                ) from exc

            wait_seconds = backoff_delay(attempt, delay)
            print(
                f"[retry] {request_label} returned a non-JSON response; "
                f"sleeping {wait_seconds:.1f}s before retry {attempt}/{max_retries}."
            )
            time.sleep(wait_seconds)

    if last_error is not None:
        raise RuntimeError(f"{request_label} failed after {max_retries} attempts") from last_error
    raise RuntimeError(f"{request_label} failed without a recoverable response")


def search_entities(
    session: requests.Session,
    name: str,
    cache: dict,
    delay: float,
    *,
    maxlag: int,
    max_retries: int,
) -> list[dict]:
    name = clean(name)
    if not name:
        return []

    cache_key = name.lower()
    if cache_key in cache:
        return cache[cache_key]

    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "uselang": "en",
        "type": "item",
        "limit": 10,
        "format": "json",
        "maxlag": maxlag,
    }

    data = request_json(
        session,
        WIKIDATA_API,
        params,
        timeout=30,
        delay=delay,
        max_retries=max_retries,
        request_label=f"wbsearchentities:{name}",
    )

    results = []
    for item in data.get("search", []):
        qid = item.get("id", "")
        if not qid.startswith("Q"):
            continue
        results.append(
            {
                "qid": qid,
                "search_label": clean(item.get("label", "")),
                "search_description": clean(item.get("description", "")),
                "search_match_text": clean(item.get("match", {}).get("text", "")),
                "search_match_type": clean(item.get("match", {}).get("type", "")),
            }
        )

    cache[cache_key] = results
    return results


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def fetch_candidate_facts(
    session: requests.Session,
    qids: list[str],
    cache: dict,
    delay: float,
    *,
    batch_size: int,
    cache_path: Path | None,
    max_retries: int,
) -> dict[str, dict]:
    qids = sorted(set(qids))
    missing = [qid for qid in qids if qid not in cache]

    for chunk_index, chunk in enumerate(chunked(missing, batch_size), start=1):
        values = " ".join(f"wd:{qid}" for qid in chunk)

        query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT
  ?item
  ?itemLabel
  ?description
  ?dob
  ?placeLabel
  ?placeCountryLabel
  ?image
  (GROUP_CONCAT(DISTINCT ?occupationLabel; separator="|") AS ?occupations)
  (GROUP_CONCAT(DISTINCT ?sportLabel; separator="|") AS ?sports)
  (GROUP_CONCAT(DISTINCT ?citizenshipLabel; separator="|") AS ?citizenships)
  (GROUP_CONCAT(DISTINCT ?teamLabel; separator="|") AS ?teams)
  (GROUP_CONCAT(DISTINCT ?positionLabel; separator="|") AS ?positions)
WHERE {{
  VALUES ?item {{ {values} }}

  OPTIONAL {{
    ?item rdfs:label ?itemLabel .
    FILTER(LANG(?itemLabel) = "en")
  }}

  OPTIONAL {{
    ?item schema:description ?description .
    FILTER(LANG(?description) = "en")
  }}

  OPTIONAL {{ ?item wdt:P569 ?dob . }}
  OPTIONAL {{
    ?item wdt:P19 ?place .
    ?place rdfs:label ?placeLabel .
    FILTER(LANG(?placeLabel) = "en")
    OPTIONAL {{
      ?place wdt:P17 ?placeCountry .
      ?placeCountry rdfs:label ?placeCountryLabel .
      FILTER(LANG(?placeCountryLabel) = "en")
    }}
  }}

  OPTIONAL {{ ?item wdt:P18 ?image . }}

  OPTIONAL {{
    ?item wdt:P106 ?occupation .
    ?occupation rdfs:label ?occupationLabel .
    FILTER(LANG(?occupationLabel) = "en")
  }}

  OPTIONAL {{
    ?item wdt:P641 ?sport .
    ?sport rdfs:label ?sportLabel .
    FILTER(LANG(?sportLabel) = "en")
  }}

  OPTIONAL {{
    ?item wdt:P27 ?citizenship .
    ?citizenship rdfs:label ?citizenshipLabel .
    FILTER(LANG(?citizenshipLabel) = "en")
  }}

  OPTIONAL {{
    ?item wdt:P54 ?team .
    ?team rdfs:label ?teamLabel .
    FILTER(LANG(?teamLabel) = "en")
  }}

  OPTIONAL {{
    ?item wdt:P413 ?position .
    ?position rdfs:label ?positionLabel .
    FILTER(LANG(?positionLabel) = "en")
  }}
}}
GROUP BY ?item ?itemLabel ?description ?dob ?placeLabel ?placeCountryLabel ?image
"""

        data = request_json(
            session,
            WIKIDATA_SPARQL,
            {"query": query, "format": "json"},
            timeout=60,
            delay=delay,
            max_retries=max_retries,
            request_label=f"SPARQL batch {chunk_index}",
            accept="application/sparql-results+json",
        )

        found = set()
        for binding in data.get("results", {}).get("bindings", []):
            item_uri = binding.get("item", {}).get("value", "")
            qid = item_uri.rsplit("/", 1)[-1]
            found.add(qid)

            cache[qid] = {
                "qid": qid,
                "label": clean(binding.get("itemLabel", {}).get("value", "")),
                "description": clean(binding.get("description", {}).get("value", "")),
                "date_of_birth": clean(binding.get("dob", {}).get("value", ""))[:10],
                "place_of_birth": clean(binding.get("placeLabel", {}).get("value", "")),
                "birth_country": clean(binding.get("placeCountryLabel", {}).get("value", "")),
                "image_url": clean(binding.get("image", {}).get("value", "")),
                "occupations": clean(binding.get("occupations", {}).get("value", "")),
                "sports": clean(binding.get("sports", {}).get("value", "")),
                "citizenships": clean(binding.get("citizenships", {}).get("value", "")),
                "teams": clean(binding.get("teams", {}).get("value", "")),
                "positions": clean(binding.get("positions", {}).get("value", "")),
            }

        for qid in chunk:
            if qid not in found and qid not in cache:
                cache[qid] = {"qid": qid}

        if cache_path is not None:
            save_cache(cache_path, cache)
        print(
            f"Fetched candidate facts for batch {chunk_index} "
            f"({len(chunk)} QIDs, {len(found)} results)."
        )

    return {qid: cache.get(qid, {"qid": qid}) for qid in qids}


def position_matches(expected_position: str, candidate_positions: str) -> bool:
    expected = norm_text(expected_position)
    positions = norm_text(candidate_positions)
    if not expected or not positions:
        return False

    keywords = {
        "goalkeeper": ["goalkeeper", "keeper"],
        "defender": ["defender", "back", "sweeper"],
        "midfielder": ["midfielder", "midfield"],
        "forward": ["forward", "striker", "winger", "attacker"],
    }

    return any(keyword in positions for keyword in keywords.get(expected, []))


def score_candidate(
    player_name: str,
    team: str,
    expected_position: str,
    search_result: dict,
    facts: dict,
) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    player_norm = norm_text(player_name)
    label = facts.get("label") or search_result.get("search_label", "")
    label_norm = norm_text(label)
    match_text_norm = norm_text(search_result.get("search_match_text", ""))

    description = " ".join(
        [
            facts.get("description", ""),
            search_result.get("search_description", ""),
        ]
    )
    description_norm = norm_text(description)

    occupations_norm = norm_text(facts.get("occupations", ""))
    sports_norm = norm_text(facts.get("sports", ""))
    citizenships_norm = norm_text(facts.get("citizenships", ""))
    teams_norm = norm_text(facts.get("teams", ""))

    if player_norm and label_norm == player_norm:
        score += 45
        reasons.append("exact_label_match")
    elif player_norm and match_text_norm == player_norm:
        score += 35
        reasons.append("exact_search_match")
    elif player_norm and (player_norm in label_norm or label_norm in player_norm):
        score += 25
        reasons.append("partial_label_match")

    football_terms = [
        "association football player",
        "footballer",
        "soccer player",
        "football player",
    ]

    if any(term in description_norm for term in football_terms):
        score += 25
        reasons.append("football_description")

    if "association football player" in occupations_norm or "football player" in occupations_norm:
        score += 35
        reasons.append("football_occupation")

    if "association football" in sports_norm or "soccer" in sports_norm:
        score += 15
        reasons.append("association_football_sport")

    aliases = TEAM_ALIASES.get(team, [team])
    alias_norms = [norm_text(alias) for alias in aliases]

    if any(alias and alias in citizenships_norm for alias in alias_norms):
        score += 20
        reasons.append("citizenship_matches_team_context")

    if any(alias and alias in teams_norm for alias in alias_norms):
        score += 30
        reasons.append("team_membership_matches_team_context")

    if position_matches(expected_position, facts.get("positions", "")):
        score += 10
        reasons.append("position_matches_roster_context")

    if facts.get("date_of_birth"):
        score += 5
        reasons.append("has_date_of_birth")

    if facts.get("place_of_birth"):
        score += 5
        reasons.append("has_place_of_birth")

    if facts.get("image_url"):
        score += 3
        reasons.append("has_image")

    return score, reasons


def next_review_id(existing_review_queue: pd.DataFrame) -> int:
    if existing_review_queue.empty or "review_id" not in existing_review_queue.columns:
        return 1

    max_num = 0
    for value in existing_review_queue["review_id"].dropna().astype(str):
        match = re.search(r"(\d+)$", value)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def append_note(old_note: str, new_note: str) -> str:
    old_note = clean(old_note)
    if not old_note:
        return new_note
    if new_note in old_note:
        return old_note
    return f"{old_note} | {new_note}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", required=True, help="Path to step2 players.csv")
    parser.add_argument("--squad-entries", required=True, help="Path to step2 squad_entries.csv")
    parser.add_argument("--manual-review", default="", help="Optional existing manual_review_queue.csv")
    parser.add_argument("--outdir", default="step3_outputs")
    parser.add_argument(
        "--contact",
        required=True,
        help="Contact info for Wikimedia User-Agent, e.g. your email or project URL",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help="Delay between API requests in seconds (default: 1.0 for polite serial scraping).",
    )
    parser.add_argument(
        "--maxlag",
        type=int,
        default=DEFAULT_MAXLAG,
        help="Action API maxlag in seconds so the job backs off when Wikimedia is under load.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum retries for transient HTTP, maxlag, or rate-limit failures.",
    )
    parser.add_argument(
        "--fact-batch-size",
        type=int,
        default=DEFAULT_FACT_BATCH_SIZE,
        help="How many candidate QIDs to request in each SPARQL fact batch.",
    )
    args = parser.parse_args()

    if args.delay <= 0:
        parser.error("--delay must be greater than 0")
    if args.maxlag <= 0:
        parser.error("--maxlag must be greater than 0")
    if args.max_retries < 1:
        parser.error("--max-retries must be at least 1")
    if args.fact_batch_size < 1:
        parser.error("--fact-batch-size must be at least 1")

    contact = clean(args.contact)
    if "@" not in contact and not contact.startswith(("http://", "https://")):
        parser.error("--contact should be a real email address or project URL for Wikimedia etiquette")

    outdir = Path(args.outdir)
    cache_dir = outdir / "cache"
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    search_cache_path = cache_dir / "wikidata_search_cache.json"
    facts_cache_path = cache_dir / "wikidata_facts_cache.json"

    search_cache = load_cache(search_cache_path)
    facts_cache = load_cache(facts_cache_path)

    players = pd.read_csv(args.players, dtype=str).fillna("")
    squad_entries = pd.read_csv(args.squad_entries, dtype=str).fillna("")

    if args.manual_review:
        manual_review = pd.read_csv(args.manual_review, dtype=str).fillna("")
    else:
        manual_review = pd.DataFrame(
            columns=[
                "review_id",
                "entity_type",
                "entity_id",
                "issue_type",
                "issue_detail",
                "suggested_fix",
                "source_url",
                "priority",
                "status",
                "resolved_at",
                "notes",
            ]
        )

    player_context = (
        squad_entries[["player_id", "team", "team_code"]]
        .drop_duplicates(subset=["player_id"])
        .set_index("player_id")
    )

    session = requests.Session()
    session_headers = {
        "User-Agent": f"WorldCupPlayerTracker/0.2 ({contact}) Python requests",
        "Api-User-Agent": f"WorldCupPlayerTracker/0.2 ({contact})",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    if "@" in contact:
        session_headers["From"] = contact
    session.headers.update(session_headers)

    all_candidate_qids = set()
    player_search_results: dict[str, list[dict]] = {}

    print(
        f"Searching Wikidata for {len(players)} players with delay={args.delay:.2f}s, "
        f"maxlag={args.maxlag}, max_retries={args.max_retries}."
    )

    for player_number, (_, row) in enumerate(players.iterrows(), start=1):
        player_id = row["player_id"]
        name = row["display_name"]

        results = search_entities(
            session,
            name,
            search_cache,
            args.delay,
            maxlag=args.maxlag,
            max_retries=args.max_retries,
        )

        name_ascii = row.get("name_ascii", "")
        if norm_text(name_ascii) != norm_text(name):
            results_ascii = search_entities(
                session,
                name_ascii,
                search_cache,
                args.delay,
                maxlag=args.maxlag,
                max_retries=args.max_retries,
            )
            seen = {r["qid"] for r in results}
            for candidate in results_ascii:
                if candidate["qid"] not in seen:
                    results.append(candidate)
                    seen.add(candidate["qid"])

        player_search_results[player_id] = results

        for candidate in results:
            all_candidate_qids.add(candidate["qid"])

        if player_number % CACHE_SAVE_EVERY == 0 or player_number == len(players):
            save_cache(search_cache_path, search_cache)

        if player_number % 50 == 0 or player_number == len(players):
            print(
                f"Searched {player_number}/{len(players)} players; "
                f"candidate QIDs discovered so far: {len(all_candidate_qids)}."
            )

    save_cache(search_cache_path, search_cache)

    candidate_facts = fetch_candidate_facts(
        session=session,
        qids=sorted(all_candidate_qids),
        cache=facts_cache,
        delay=args.delay,
        batch_size=args.fact_batch_size,
        cache_path=facts_cache_path,
        max_retries=args.max_retries,
    )
    save_cache(facts_cache_path, facts_cache)

    candidate_rows = []
    review_rows = []
    review_counter = next_review_id(manual_review)

    enriched = players.copy()

    for idx, row in enriched.iterrows():
        player_id = row["player_id"]
        player_name = row["display_name"]
        expected_position = row.get("primary_position", "")

        if player_id not in player_context.index:
            team = ""
            team_code = ""
        else:
            team = player_context.loc[player_id, "team"]
            team_code = player_context.loc[player_id, "team_code"]

        scored_candidates = []
        for search_result in player_search_results.get(player_id, []):
            qid = search_result["qid"]
            facts = candidate_facts.get(qid, {"qid": qid})
            score, reasons = score_candidate(
                player_name,
                team,
                expected_position,
                search_result,
                facts,
            )

            scored_candidates.append(
                {
                    "player_id": player_id,
                    "team": team,
                    "team_code": team_code,
                    "display_name": player_name,
                    "candidate_qid": qid,
                    "candidate_url": wikidata_url(qid),
                    "candidate_label": facts.get("label") or search_result.get("search_label", ""),
                    "candidate_description": facts.get("description") or search_result.get("search_description", ""),
                    "date_of_birth": facts.get("date_of_birth", ""),
                    "place_of_birth": facts.get("place_of_birth", ""),
                    "birth_country": facts.get("birth_country", ""),
                    "citizenships": facts.get("citizenships", ""),
                    "teams": facts.get("teams", ""),
                    "occupations": facts.get("occupations", ""),
                    "sports": facts.get("sports", ""),
                    "positions": facts.get("positions", ""),
                    "image_url": facts.get("image_url", ""),
                    "match_score": score,
                    "match_reasons": "|".join(reasons),
                }
            )

        scored_candidates.sort(key=lambda d: d["match_score"], reverse=True)
        candidate_rows.extend(scored_candidates)

        best = scored_candidates[0] if scored_candidates else None
        second = scored_candidates[1] if len(scored_candidates) > 1 else None
        second_score = second["match_score"] if second else 0
        margin = best["match_score"] - second_score if best else 0

        if best and best["match_score"] >= AUTO_MATCH_SCORE and margin >= AUTO_MATCH_MARGIN:
            qid = best["candidate_qid"]
            facts = candidate_facts.get(qid, {})

            enriched.at[idx, "wikidata_id"] = qid

            if not enriched.at[idx, "date_of_birth"]:
                enriched.at[idx, "date_of_birth"] = facts.get("date_of_birth", "")

            if not enriched.at[idx, "place_of_birth"]:
                enriched.at[idx, "place_of_birth"] = facts.get("place_of_birth", "")

            if not enriched.at[idx, "birth_country"]:
                enriched.at[idx, "birth_country"] = facts.get("birth_country", "")

            if not enriched.at[idx, "image_url"]:
                enriched.at[idx, "image_url"] = facts.get("image_url", "")

            if not enriched.at[idx, "image_commons_title"]:
                enriched.at[idx, "image_commons_title"] = image_title_from_url(facts.get("image_url", ""))

            if not enriched.at[idx, "bio_source_url"]:
                enriched.at[idx, "bio_source_url"] = wikidata_url(qid)

            enriched.at[idx, "data_confidence"] = "wikidata_auto_match_high"
            enriched.at[idx, "manual_review_flag"] = "FALSE"
            enriched.at[idx, "notes"] = append_note(
                enriched.at[idx, "notes"],
                f"Auto-matched to Wikidata {qid}; score={best['match_score']}; margin={margin}",
            )

            if not facts.get("date_of_birth") or not facts.get("place_of_birth"):
                review_rows.append(
                    {
                        "review_id": f"rev_{review_counter:05d}",
                        "entity_type": "player",
                        "entity_id": player_id,
                        "issue_type": "missing_wikidata_bio_field",
                        "issue_detail": f"Auto-matched player {player_name} to {qid}, but date of birth or place of birth is missing.",
                        "suggested_fix": "Check Wikidata, FIFA profile, federation profile, or reliable biography source.",
                        "source_url": wikidata_url(qid),
                        "priority": "medium",
                        "status": "open",
                        "resolved_at": "",
                        "notes": "",
                    }
                )
                review_counter += 1

        elif best:
            enriched.at[idx, "manual_review_flag"] = "TRUE"
            enriched.at[idx, "data_confidence"] = "wikidata_match_needs_review"
            enriched.at[idx, "notes"] = append_note(
                enriched.at[idx, "notes"],
                f"Needs Wikidata review; top candidate={best['candidate_qid']}; score={best['match_score']}; margin={margin}",
            )

            issue_type = "ambiguous_wikidata_match" if second else "low_confidence_wikidata_match"
            review_rows.append(
                {
                    "review_id": f"rev_{review_counter:05d}",
                    "entity_type": "player",
                    "entity_id": player_id,
                    "issue_type": issue_type,
                    "issue_detail": f"{player_name} needs manual Wikidata review. Top candidate {best['candidate_qid']} scored {best['match_score']} with margin {margin}.",
                    "suggested_fix": f"Review candidate {wikidata_url(best['candidate_qid'])}. If correct, copy {best['candidate_qid']} into players.wikidata_id.",
                    "source_url": wikidata_url(best["candidate_qid"]),
                    "priority": "high" if best["match_score"] >= 70 else "medium",
                    "status": "open",
                    "resolved_at": "",
                    "notes": "",
                }
            )
            review_counter += 1

        else:
            enriched.at[idx, "manual_review_flag"] = "TRUE"
            enriched.at[idx, "data_confidence"] = "wikidata_no_match"
            enriched.at[idx, "notes"] = append_note(enriched.at[idx, "notes"], "No Wikidata candidates found.")

            review_rows.append(
                {
                    "review_id": f"rev_{review_counter:05d}",
                    "entity_type": "player",
                    "entity_id": player_id,
                    "issue_type": "no_wikidata_match",
                    "issue_detail": f"No Wikidata candidates found for {player_name}.",
                    "suggested_fix": "Search Wikidata manually using alternate spellings, accents, or full legal name.",
                    "source_url": "",
                    "priority": "medium",
                    "status": "open",
                    "resolved_at": "",
                    "notes": "",
                }
            )
            review_counter += 1

    candidate_matches = pd.DataFrame(candidate_rows)

    new_reviews = pd.DataFrame(review_rows)
    manual_review_step3 = pd.concat([manual_review, new_reviews], ignore_index=True)

    summary = {
        "total_players": len(enriched),
        "auto_matched": int((enriched["data_confidence"] == "wikidata_auto_match_high").sum()),
        "needs_review": int((enriched["manual_review_flag"] == "TRUE").sum()),
        "no_match": int((enriched["data_confidence"] == "wikidata_no_match").sum()),
        "candidate_rows": len(candidate_matches),
        "new_review_items": len(new_reviews),
    }

    summary_df = pd.DataFrame([summary])

    enriched.to_csv(outdir / "players_wikidata_enriched.csv", index=False, encoding="utf-8-sig")
    candidate_matches.to_csv(outdir / "wikidata_candidate_matches.csv", index=False, encoding="utf-8-sig")
    manual_review_step3.to_csv(outdir / "manual_review_queue_step3.csv", index=False, encoding="utf-8-sig")
    summary_df.to_csv(outdir / "wikidata_match_summary.csv", index=False, encoding="utf-8-sig")

    print("Wrote Step 3 outputs:")
    print(f"- {outdir / 'players_wikidata_enriched.csv'}")
    print(f"- {outdir / 'wikidata_candidate_matches.csv'}")
    print(f"- {outdir / 'manual_review_queue_step3.csv'}")
    print(f"- {outdir / 'wikidata_match_summary.csv'}")
    print()
    print(summary_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
