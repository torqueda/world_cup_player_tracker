#!/usr/bin/env python3

import argparse
import csv
import re
import time
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

USER_AGENT = "world-cup-2026-player-club-map-step6/0.1 (personal research project)"


def normalize_name(value: str) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\b(f\.?c\.?|s\.?k\.?|a\.?f\.?c\.?|club|cf|sc|ac|fk)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def slim_query_variants(club_name: str, club_name_ascii: str) -> list[str]:
    names = []
    for value in [club_name, club_name_ascii]:
        if pd.notna(value) and str(value).strip():
            names.append(str(value).strip())

    variants = set(names)
    for name in names:
        stripped = re.sub(r"\b(F\.?C\.?|S\.?K\.?|A\.?F\.?C\.?|Club|CF|SC|AC|FK)\b\.?", "", name, flags=re.I)
        stripped = re.sub(r"\s+", " ", stripped).strip(" -,.")
        if stripped:
            variants.add(stripped)
        variants.add(f"{stripped} football club".strip())

    return [v for v in variants if v]


def wikidata_search(query: str, limit: int = 5) -> list[dict]:
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "uselang": "en",
        "type": "item",
        "limit": limit,
        "search": query,
    }
    r = requests.get(
        WIKIDATA_API,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("search", [])


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def parse_wkt_point(value):
    if not value or pd.isna(value):
        return None, None
    match = re.search(r"Point\(([-0-9.]+)\s+([-0-9.]+)\)", str(value))
    if not match:
        return None, None
    lon = float(match.group(1))
    lat = float(match.group(2))
    return lat, lon


def fetch_candidate_details(qids: list[str]) -> dict[str, list[dict]]:
    if not qids:
        return {}

    details_by_qid = defaultdict(list)

    for batch in chunked(qids, 40):
        values = " ".join(f"wd:{qid}" for qid in batch)

        query = f"""
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wikibase: <http://wikiba.se/ontology#>
        PREFIX bd: <http://www.bigdata.com/rdf#>
        PREFIX schema: <http://schema.org/>

        SELECT ?club ?clubLabel ?clubDescription
               ?instanceOfLabel
               ?countryLabel ?leagueLabel
               ?stadium ?stadiumLabel ?stadiumCoord
               ?cityLabel
               ?clubCoord
               ?enwiki
        WHERE {{
          VALUES ?club {{ {values} }}

          OPTIONAL {{ ?club wdt:P31 ?instanceOf. }}
          OPTIONAL {{ ?club wdt:P17 ?country. }}
          OPTIONAL {{ ?club wdt:P118 ?league. }}

          OPTIONAL {{
            ?club wdt:P115 ?stadium.
            OPTIONAL {{ ?stadium wdt:P625 ?stadiumCoord. }}
            OPTIONAL {{ ?stadium wdt:P131 ?city. }}
          }}

          OPTIONAL {{ ?club wdt:P625 ?clubCoord. }}

          OPTIONAL {{
            ?enwiki schema:about ?club ;
                    schema:isPartOf <https://en.wikipedia.org/> .
          }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
            ?club rdfs:label ?clubLabel.
            ?club schema:description ?clubDescription.
            ?instanceOf rdfs:label ?instanceOfLabel.
            ?country rdfs:label ?countryLabel.
            ?league rdfs:label ?leagueLabel.
            ?stadium rdfs:label ?stadiumLabel.
            ?city rdfs:label ?cityLabel.
          }}
        }}
        """

        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=60,
        )
        r.raise_for_status()

        for row in r.json()["results"]["bindings"]:
            club_uri = row.get("club", {}).get("value", "")
            qid = club_uri.rsplit("/", 1)[-1]

            stadium_uri = row.get("stadium", {}).get("value", "")
            stadium_qid = stadium_uri.rsplit("/", 1)[-1] if stadium_uri else ""

            stadium_lat, stadium_lon = parse_wkt_point(row.get("stadiumCoord", {}).get("value"))
            club_lat, club_lon = parse_wkt_point(row.get("clubCoord", {}).get("value"))

            details_by_qid[qid].append({
                "wikidata_id": qid,
                "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
                "wikidata_label": row.get("clubLabel", {}).get("value", ""),
                "wikidata_description": row.get("clubDescription", {}).get("value", ""),
                "instance_of": row.get("instanceOfLabel", {}).get("value", ""),
                "country": row.get("countryLabel", {}).get("value", ""),
                "league": row.get("leagueLabel", {}).get("value", ""),
                "stadium_wikidata_id": stadium_qid,
                "stadium": row.get("stadiumLabel", {}).get("value", ""),
                "city": row.get("cityLabel", {}).get("value", ""),
                "stadium_lat": stadium_lat,
                "stadium_lon": stadium_lon,
                "club_lat": club_lat,
                "club_lon": club_lon,
                "wikipedia_url": row.get("enwiki", {}).get("value", ""),
            })

        time.sleep(0.25)

    return details_by_qid


def score_candidate(club_name, club_name_ascii, candidate):
    name_norms = [normalize_name(club_name), normalize_name(club_name_ascii)]
    label_norm = normalize_name(candidate.get("wikidata_label", ""))

    best_name_score = max(
        SequenceMatcher(None, n, label_norm).ratio()
        for n in name_norms
        if n
    ) if label_norm else 0

    description = (candidate.get("wikidata_description") or "").lower()
    instance_of = (candidate.get("instance_of") or "").lower()

    score = 0
    score += round(best_name_score * 45)

    if label_norm in name_norms:
        score += 25

    if "football" in description or "soccer" in description:
        score += 15

    if "association football club" in instance_of or "football club" in instance_of:
        score += 20
    elif "sports club" in instance_of or "association football" in instance_of:
        score += 10

    if candidate.get("stadium"):
        score += 10

    if candidate.get("stadium_lat") is not None and candidate.get("stadium_lon") is not None:
        score += 15

    if candidate.get("wikipedia_url"):
        score += 5

    return min(score, 100)


def best_candidate_rows(clubs_df):
    all_search_qids = defaultdict(dict)

    for _, club in clubs_df.iterrows():
        club_id = club["club_id"]
        queries = slim_query_variants(club.get("club_name", ""), club.get("club_name_ascii", ""))

        for query in queries:
            try:
                results = wikidata_search(query, limit=5)
            except Exception as exc:
                print(f"Search failed for {club_id} / {query}: {exc}")
                continue

            for rank, result in enumerate(results, start=1):
                qid = result.get("id")
                if not qid:
                    continue
                all_search_qids[club_id][qid] = {
                    "search_query": query,
                    "search_rank": rank,
                    "search_label": result.get("label", ""),
                    "search_description": result.get("description", ""),
                }

            time.sleep(0.2)

    unique_qids = sorted({qid for qids in all_search_qids.values() for qid in qids})
    details = fetch_candidate_details(unique_qids)

    candidate_rows = []

    for _, club in clubs_df.iterrows():
        club_id = club["club_id"]
        club_name = club.get("club_name", "")
        club_name_ascii = club.get("club_name_ascii", "")

        for qid, search_meta in all_search_qids.get(club_id, {}).items():
            detail_rows = details.get(qid) or [{
                "wikidata_id": qid,
                "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
                "wikidata_label": search_meta.get("search_label", ""),
                "wikidata_description": search_meta.get("search_description", ""),
                "instance_of": "",
                "country": "",
                "league": "",
                "stadium_wikidata_id": "",
                "stadium": "",
                "city": "",
                "stadium_lat": None,
                "stadium_lon": None,
                "club_lat": None,
                "club_lon": None,
                "wikipedia_url": "",
            }]

            for detail in detail_rows:
                score = score_candidate(club_name, club_name_ascii, detail)
                row = {
                    "club_id": club_id,
                    "club_name": club_name,
                    "club_name_ascii": club_name_ascii,
                    "candidate_score": score,
                    **search_meta,
                    **detail,
                }
                candidate_rows.append(row)

    return pd.DataFrame(candidate_rows)


def classify_best_candidates(candidates_df):
    if candidates_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    sort_cols = ["club_id", "candidate_score", "search_rank"]
    candidates_df = candidates_df.sort_values(sort_cols, ascending=[True, False, True]).copy()

    best_rows = []

    for club_id, group in candidates_df.groupby("club_id"):
        group = group.sort_values(["candidate_score", "search_rank"], ascending=[False, True])
        best = group.iloc[0].copy()

        top_score = best["candidate_score"]
        second_score = group.iloc[1]["candidate_score"] if len(group) > 1 else 0
        score_gap = top_score - second_score

        has_stadium_coords = pd.notna(best.get("stadium_lat")) and pd.notna(best.get("stadium_lon"))
        has_club_coords = pd.notna(best.get("club_lat")) and pd.notna(best.get("club_lon"))

        if top_score >= 80 and score_gap >= 8 and has_stadium_coords:
            status = "auto_candidate_high_stadium_coords"
            review_flag = False
            reason = ""
        elif top_score >= 75 and score_gap >= 8 and (has_stadium_coords or has_club_coords):
            status = "auto_candidate_medium_coords"
            review_flag = True
            reason = "Good club candidate, but coordinate basis needs review."
        elif top_score >= 70 and score_gap >= 8:
            status = "candidate_no_coordinates"
            review_flag = True
            reason = "Club candidate found, but no usable coordinates found."
        else:
            status = "needs_manual_match_review"
            review_flag = True
            reason = "Low score, ambiguous candidate set, or no confident Wikidata match."

        coord_basis = ""
        geo_source_url = ""
        final_lat = ""
        final_lon = ""

        if has_stadium_coords:
            coord_basis = "wikidata_home_venue_stadium_P115_to_stadium_P625"
            final_lat = best.get("stadium_lat")
            final_lon = best.get("stadium_lon")
            if best.get("stadium_wikidata_id"):
                geo_source_url = f"https://www.wikidata.org/wiki/{best.get('stadium_wikidata_id')}"
        elif has_club_coords:
            coord_basis = "wikidata_club_coordinate_P625_review_needed"
            final_lat = best.get("club_lat")
            final_lon = best.get("club_lon")
            geo_source_url = best.get("wikidata_url")

        best["match_status"] = status
        best["manual_review_flag"] = "TRUE" if review_flag else "FALSE"
        best["review_reason"] = reason
        best["coordinate_basis"] = coord_basis
        best["geo_source_url"] = geo_source_url
        best["proposed_club_lat"] = final_lat
        best["proposed_club_lon"] = final_lon

        best["approved_wikidata_id"] = ""
        best["approved_stadium"] = ""
        best["approved_lat"] = ""
        best["approved_lon"] = ""
        best["approved_geo_source_url"] = ""
        best["manual_notes"] = ""

        best_rows.append(best)

    working_df = pd.DataFrame(best_rows)
    review_df = working_df[working_df["manual_review_flag"] == "TRUE"].copy()

    return working_df, review_df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook",
        default="world_cup_2026_player_map_master_manually_reviewed.xlsx",
        help="Path to latest master workbook export.",
    )
    parser.add_argument(
        "--outdir",
        default="step6_working_outputs",
        help="Output folder.",
    )
    args = parser.parse_args()

    workbook_path = Path(args.workbook)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    clubs_df = pd.read_excel(workbook_path, sheet_name="clubs", dtype=str)
    player_club_df = pd.read_excel(workbook_path, sheet_name="player_club_at_callup", dtype=str)

    required_club_cols = {"club_id", "club_name", "club_name_ascii"}
    missing = required_club_cols - set(clubs_df.columns)
    if missing:
        raise ValueError(f"clubs sheet missing required columns: {sorted(missing)}")

    if "club_id" not in player_club_df.columns:
        raise ValueError("player_club_at_callup sheet missing club_id column")

    clubs_df["club_id"] = clubs_df["club_id"].astype(str)
    player_club_df["club_id"] = player_club_df["club_id"].astype(str)

    player_counts = player_club_df.groupby("club_id").size().rename("player_count").reset_index()
    clubs_df = clubs_df.merge(player_counts, on="club_id", how="left")
    clubs_df["player_count"] = clubs_df["player_count"].fillna(0).astype(int)

    if clubs_df["club_id"].duplicated().any():
        dupes = clubs_df[clubs_df["club_id"].duplicated(keep=False)]["club_id"].tolist()
        raise ValueError(f"Duplicate club_id values found: {dupes[:20]}")

    missing_refs = sorted(set(player_club_df["club_id"]) - set(clubs_df["club_id"]))
    if missing_refs:
        raise ValueError(f"player_club_at_callup references missing club IDs: {missing_refs[:20]}")

    candidates_df = best_candidate_rows(clubs_df)
    working_df, review_df = classify_best_candidates(candidates_df)

    clubs_df.to_csv(outdir / "clubs_step6_input_snapshot.csv", index=False)
    candidates_df.to_csv(outdir / "club_wikidata_candidates_step6.csv", index=False)
    working_df.to_csv(outdir / "clubs_step6_working.csv", index=False)
    review_df.to_csv(outdir / "club_geocoding_review_queue.csv", index=False)

    summary_rows = [
        {"metric": "clubs_input_rows", "value": len(clubs_df)},
        {"metric": "wikidata_candidate_rows", "value": len(candidates_df)},
        {"metric": "working_rows", "value": len(working_df)},
        {"metric": "review_queue_rows", "value": len(review_df)},
        {"metric": "auto_high_stadium_coords_rows", "value": int((working_df["match_status"] == "auto_candidate_high_stadium_coords").sum()) if not working_df.empty else 0},
        {"metric": "medium_or_review_rows", "value": len(review_df)},
    ]
    pd.DataFrame(summary_rows).to_csv(outdir / "step6_match_summary.csv", index=False)

    print("Wrote Step 6 working outputs to:", outdir)
    print(pd.DataFrame(summary_rows).to_string(index=False))


if __name__ == "__main__":
    main()