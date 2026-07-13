#!/usr/bin/env python3
"""
Validate current player Wikidata IDs against roster context.

This is a Step 3b / QA script. It does not modify your data.

Inputs:
  --players players_image_metadata_enriched.csv
  --squad-entries squad_entries.csv
  --player-club player_club_at_callup.csv

Outputs:
  player_identity_validation.csv
  player_identity_validation_summary.csv
  player_identity_validation_review_queue.csv

Checks:
  - QID exists and is a human footballer/soccer player where possible
  - Wikidata label/aliases resemble display_name
  - Wikidata date of birth matches players.date_of_birth after normalization
  - age is plausible for a 2026 World Cup roster
  - citizenship/team context loosely matches the national team
  - source club appears in Wikidata P54 team list where available
    (club mismatch is a warning, not automatic failure, because P54 is often incomplete)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dateutil import parser


WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

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


def clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    value = str(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ascii_fold(value: str) -> str:
    value = clean(value)
    value = unicodedata.normalize("NFKD", value)
    return value.encode("ascii", "ignore").decode("ascii")


def norm(value: str) -> str:
    value = ascii_fold(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_qid(value: str) -> str:
    value = clean(value).upper()
    match = re.search(r"Q\d+", value)
    return match.group(0) if match else ""


def parse_date_to_iso(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    try:
        dt = parser.parse(value, dayfirst=False, yearfirst=False, fuzzy=False)
        return dt.date().isoformat()
    except Exception:
        return ""


def year_from_iso(value: str) -> int | None:
    if not value or not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return None
    return int(value[:4])


def wikidata_url(qid: str) -> str:
    return f"https://www.wikidata.org/wiki/{qid}" if qid else ""


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_facts(session: requests.Session, qids: list[str], cache: dict, delay: float) -> dict[str, dict]:
    qids = sorted({normalize_qid(qid) for qid in qids if normalize_qid(qid)})
    missing = [qid for qid in qids if qid not in cache]

    for part in chunked(missing, 40):
        values = " ".join(f"wd:{qid}" for qid in part)
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
  (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
  (GROUP_CONCAT(DISTINCT ?occupationLabel; separator="|") AS ?occupations)
  (GROUP_CONCAT(DISTINCT ?sportLabel; separator="|") AS ?sports)
  (GROUP_CONCAT(DISTINCT ?citizenshipLabel; separator="|") AS ?citizenships)
  (GROUP_CONCAT(DISTINCT ?teamLabel; separator="|") AS ?teams)
  (GROUP_CONCAT(DISTINCT ?positionLabel; separator="|") AS ?positions)
WHERE {{
  VALUES ?item {{ {values} }}

  OPTIONAL {{ ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) = "en") }}
  OPTIONAL {{ ?item schema:description ?description . FILTER(LANG(?description) = "en") }}
  OPTIONAL {{ ?item wdt:P569 ?dob . }}

  OPTIONAL {{ ?item skos:altLabel ?alias . FILTER(LANG(?alias) = "en") }}

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
GROUP BY ?item ?itemLabel ?description ?dob
"""
        response = session.get(
            WIKIDATA_SPARQL,
            params={"query": query, "format": "json"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        found = set()
        for binding in data.get("results", {}).get("bindings", []):
            qid = binding.get("item", {}).get("value", "").rsplit("/", 1)[-1]
            found.add(qid)
            cache[qid] = {
                "qid": qid,
                "label": clean(binding.get("itemLabel", {}).get("value", "")),
                "description": clean(binding.get("description", {}).get("value", "")),
                "date_of_birth": clean(binding.get("dob", {}).get("value", ""))[:10],
                "aliases": clean(binding.get("aliases", {}).get("value", "")),
                "occupations": clean(binding.get("occupations", {}).get("value", "")),
                "sports": clean(binding.get("sports", {}).get("value", "")),
                "citizenships": clean(binding.get("citizenships", {}).get("value", "")),
                "teams": clean(binding.get("teams", {}).get("value", "")),
                "positions": clean(binding.get("positions", {}).get("value", "")),
            }

        for qid in part:
            if qid not in found:
                cache[qid] = {"qid": qid}

        time.sleep(delay)

    return {qid: cache.get(qid, {"qid": qid}) for qid in qids}


def best_name_similarity(display_name: str, label: str, aliases: str) -> float:
    names = [label] + [x for x in aliases.split("|") if x]
    display = norm(display_name)
    if not display:
        return 0.0
    return max((SequenceMatcher(None, display, norm(name)).ratio() for name in names if norm(name)), default=0.0)


def contains_any(haystack: str, needles: list[str]) -> bool:
    hay = norm(haystack)
    return any(norm(needle) and norm(needle) in hay for needle in needles)


def score_and_flags(row: pd.Series, facts: dict) -> tuple[int, list[str], list[str]]:
    score = 0
    flags = []

    display_name = row["display_name"]
    team = row["team"]
    club = row["club_name_at_source"]
    local_dob_iso = row["date_of_birth_iso"]

    sim = best_name_similarity(display_name, facts.get("label", ""), facts.get("aliases", ""))
    if sim >= 0.92:
        score += 30
    elif sim >= 0.75:
        score += 15
        flags.append("name_similarity_medium")
    else:
        flags.append("name_similarity_low")

    desc_blob = " ".join([facts.get("description", ""), facts.get("occupations", ""), facts.get("sports", "")])
    if any(term in norm(desc_blob) for term in ["association football player", "footballer", "football player", "soccer player", "association football"]):
        score += 25
    else:
        flags.append("not_clearly_footballer")

    aliases = TEAM_ALIASES.get(team, [team])
    if contains_any(facts.get("citizenships", ""), aliases) or contains_any(facts.get("teams", ""), aliases):
        score += 20
    else:
        flags.append("team_or_citizenship_context_not_found")

    # Club match is only a soft signal: Wikidata P54 is often incomplete or stale.
    if club and contains_any(facts.get("teams", ""), [club]):
        score += 10
    else:
        flags.append("source_club_not_in_wikidata_p54_soft_warning")

    wd_dob = facts.get("date_of_birth", "")
    if local_dob_iso and wd_dob and local_dob_iso == wd_dob:
        score += 15
    elif local_dob_iso and wd_dob and local_dob_iso != wd_dob:
        flags.append("dob_mismatch_with_wikidata")
    elif not local_dob_iso:
        flags.append("local_dob_unparseable")
    elif not wd_dob:
        flags.append("wikidata_missing_dob")

    year = year_from_iso(local_dob_iso)
    if year is None:
        flags.append("dob_year_missing")
    elif year < 1900 or year > 2010:
        flags.append("dob_year_implausible")
    elif year < 1986:
        flags.append("birth_year_before_1986_spot_check")
    elif year > 2010:
        flags.append("birth_year_after_2010_spot_check")

    return score, flags, [f"name_similarity={sim:.3f}"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", required=True)
    parser.add_argument("--squad-entries", required=True)
    parser.add_argument("--player-club", required=True)
    parser.add_argument("--outdir", default="identity_validation_outputs")
    parser.add_argument("--contact", required=True)
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    cache_dir = outdir / "cache"
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    players = pd.read_csv(args.players, dtype=str).fillna("")
    squad = pd.read_csv(args.squad_entries, dtype=str).fillna("")
    pc = pd.read_csv(args.player_club, dtype=str).fillna("")

    context = (
        squad[["player_id", "team", "team_code", "position_group"]]
        .drop_duplicates("player_id")
        .merge(
            pc[["player_id", "club_name_at_source"]].drop_duplicates("player_id"),
            on="player_id",
            how="left",
        )
    )

    data = players.merge(context, on="player_id", how="left")
    data["wikidata_id"] = data["wikidata_id"].map(normalize_qid)
    data["date_of_birth_iso"] = data["date_of_birth"].map(parse_date_to_iso)

    session = requests.Session()
    session.headers.update({
        "User-Agent": f"WorldCupPlayerMap/0.1 ({args.contact}) Python requests",
        "Accept": "application/json",
    })

    cache_path = cache_dir / "wikidata_identity_facts_cache.json"
    cache = load_cache(cache_path)
    facts_by_qid = fetch_facts(session, data["wikidata_id"].tolist(), cache, args.delay)
    save_cache(cache_path, cache)

    rows = []
    review_rows = []

    for _, row in data.iterrows():
        qid = row["wikidata_id"]
        facts = facts_by_qid.get(qid, {"qid": qid})
        score, flags, detail_bits = score_and_flags(row, facts)

        severity = "ok"
        if "dob_year_implausible" in flags or "dob_mismatch_with_wikidata" in flags or "not_clearly_footballer" in flags:
            severity = "high"
        elif "name_similarity_low" in flags or "team_or_citizenship_context_not_found" in flags:
            severity = "medium"
        elif "source_club_not_in_wikidata_p54_soft_warning" in flags or "birth_year_before_1986_spot_check" in flags:
            severity = "low"

        output_row = {
            "severity": severity,
            "validation_score": score,
            "flags": "|".join(flags),
            "details": "|".join(detail_bits),
            "player_id": row["player_id"],
            "display_name": row["display_name"],
            "team": row.get("team", ""),
            "team_code": row.get("team_code", ""),
            "club_name_at_source": row.get("club_name_at_source", ""),
            "local_date_of_birth": row["date_of_birth"],
            "local_date_of_birth_iso": row["date_of_birth_iso"],
            "wikidata_id": qid,
            "wikidata_url": wikidata_url(qid),
            "wikidata_label": facts.get("label", ""),
            "wikidata_description": facts.get("description", ""),
            "wikidata_date_of_birth": facts.get("date_of_birth", ""),
            "wikidata_citizenships": facts.get("citizenships", ""),
            "wikidata_teams_p54": facts.get("teams", ""),
            "wikidata_occupations": facts.get("occupations", ""),
            "wikidata_sports": facts.get("sports", ""),
        }
        rows.append(output_row)

        if severity in {"high", "medium"}:
            review_rows.append({
                "player_id": row["player_id"],
                "display_name": row["display_name"],
                "team": row.get("team", ""),
                "club_name_at_source": row.get("club_name_at_source", ""),
                "wikidata_id": qid,
                "severity": severity,
                "flags": "|".join(flags),
                "suggested_action": "Open the Wikidata URL and compare against roster source, club, DOB, and national team context.",
                "wikidata_url": wikidata_url(qid),
            })

    validation = pd.DataFrame(rows).sort_values(["severity", "validation_score"], ascending=[True, True])
    review = pd.DataFrame(review_rows).sort_values(["severity", "display_name"], ascending=[True, True])
    summary = pd.DataFrame([{
        "total_players": len(validation),
        "high_review_items": int((validation["severity"] == "high").sum()),
        "medium_review_items": int((validation["severity"] == "medium").sum()),
        "low_warnings": int((validation["severity"] == "low").sum()),
        "ok": int((validation["severity"] == "ok").sum()),
    }])

    validation.to_csv(outdir / "player_identity_validation.csv", index=False, encoding="utf-8-sig")
    review.to_csv(outdir / "player_identity_validation_review_queue.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(outdir / "player_identity_validation_summary.csv", index=False, encoding="utf-8-sig")

    print("Wrote:")
    print(outdir / "player_identity_validation.csv")
    print(outdir / "player_identity_validation_review_queue.csv")
    print(outdir / "player_identity_validation_summary.csv")
    print()
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
