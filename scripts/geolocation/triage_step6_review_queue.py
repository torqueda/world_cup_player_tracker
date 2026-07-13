#!/usr/bin/env python3
"""
Classify Step 6 club geolocation review rows into smaller, action-oriented buckets.

This script is read-only with respect to source inputs. It reads the existing Step 6
working CSVs and writes triage artifacts that help reduce manual workload by:
1. Flagging high-confidence stadium-coordinate rows that can be batch-approved.
2. Separating likely wrong/non-club candidates from valid clubs that only need
   coordinate backfill.
3. Surfacing hard manual-search cases in a small bucket.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


BAD_ENTITY_HINTS = {
    "album",
    "asteroid",
    "band",
    "company",
    "district",
    "family name",
    "film",
    "given name",
    "horse",
    "human",
    "municipality",
    "person",
    "province",
    "railway station",
    "running event",
    "school",
    "settlement",
    "ship",
    "song",
    "sports discipline",
    "star system",
    "submarine",
    "surname",
    "taxon",
    "town",
    "university",
    "village",
}

WRONG_SPORT_HINTS = {
    "australian rules",
    "baseball",
    "basketball",
    "cricket",
    "field hockey",
    "handball",
    "ice hockey",
    "rugby",
    "volleyball",
    "water polo",
}

FOOTBALL_HINTS = {
    "association football",
    "football club",
    "soccer club",
    "soccer team",
    "football team",
    "footballer",
    "soccer",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\b(f\.?c\.?|a\.?f\.?c\.?|s\.?c\.?|a\.?c\.?|f\.?k\.?|club)\b", " ", text)
    text = re.sub(r"\b(football club|soccer club|sporting club)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def numeric_int(value: str, default: int = 0) -> int:
    try:
        if str(value).strip() == "":
            return default
        return int(float(str(value)))
    except Exception:
        return default


def ascii_fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def strip_parenthetical(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", " ", value or "").strip()


def build_manual_search_hint(club_name: str) -> str:
    base = strip_parenthetical(club_name)
    base = re.sub(r"\s+", " ", base).strip(" -,.")
    folded = ascii_fold(base)
    suggestions = []
    for candidate in [base, folded]:
        candidate = candidate.strip()
        if candidate and candidate not in suggestions:
            suggestions.append(candidate)
        if candidate:
            suggestions.append(f"{candidate} FC")
            suggestions.append(f"{candidate} football club")

    deduped = []
    seen = set()
    for item in suggestions:
        key = item.lower()
        if item and key not in seen:
            deduped.append(item)
            seen.add(key)
    return " | ".join(deduped[:3])


def combined_text(row: Dict[str, str]) -> str:
    parts = [
        row.get("wikidata_label", ""),
        row.get("wikidata_description", ""),
        row.get("search_label", ""),
        row.get("search_description", ""),
        row.get("instance_of", ""),
    ]
    return " ".join(parts).lower()


def is_women_entity(row: Dict[str, str]) -> bool:
    return "women" in combined_text(row)


def is_wrong_sport_entity(row: Dict[str, str]) -> bool:
    text = combined_text(row)
    return any(hint in text for hint in WRONG_SPORT_HINTS)


def is_non_club_entity(row: Dict[str, str]) -> bool:
    text = combined_text(row)
    football_like = any(hint in text for hint in FOOTBALL_HINTS)
    if is_wrong_sport_entity(row):
        return True
    return any(hint in text for hint in BAD_ENTITY_HINTS) and not football_like


def looks_like_football_club(row: Dict[str, str]) -> bool:
    text = combined_text(row)
    if is_wrong_sport_entity(row):
        return False
    return any(hint in text for hint in FOOTBALL_HINTS) or "sports club" in text


def exact_normalized_match(club_name: str, wikidata_label: str) -> bool:
    club_norm = normalize_name(club_name)
    label_norm = normalize_name(wikidata_label)
    return bool(club_norm and label_norm and club_norm == label_norm)


def token_count(value: str) -> int:
    norm = normalize_name(value)
    return len(norm.split()) if norm else 0


def sort_candidates(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            -numeric_int(row.get("candidate_score", "")),
            numeric_int(row.get("search_rank", ""), default=999),
        ),
    )


def triage_row(review_row: Dict[str, str], club_candidates: List[Dict[str, str]]) -> Tuple[str, str, str, str, str]:
    score = numeric_int(review_row.get("candidate_score", ""))
    rank = numeric_int(review_row.get("search_rank", ""), default=999)
    players = numeric_int(review_row.get("player_count", ""))
    exact_match = exact_normalized_match(review_row.get("club_name", ""), review_row.get("wikidata_label", ""))
    tokens = token_count(review_row.get("club_name", ""))
    women_flag = is_women_entity(review_row)
    non_club_flag = is_non_club_entity(review_row)
    football_like = looks_like_football_club(review_row)
    status = review_row.get("match_status", "")

    second_label = ""
    second_score = ""
    score_gap = ""
    if len(club_candidates) > 1:
        second_label = club_candidates[1].get("wikidata_label", "")
        second_score = str(numeric_int(club_candidates[1].get("candidate_score", "")))
        score_gap = str(score - numeric_int(club_candidates[1].get("candidate_score", "")))

    if status == "candidate_stadium_coords_needs_spotcheck":
        if exact_match and tokens >= 2 and score >= 95 and rank == 1 and not women_flag and not non_club_flag:
            bucket = "batch_approve_stadium_coords"
            reason = "Multi-token exact match, top-ranked candidate, high score, and stadium coordinates already present."
        elif women_flag:
            bucket = "manual_review_gender_team_mismatch"
            reason = "Top candidate appears to be a women's team and should be checked against the men's club."
        else:
            bucket = "manual_review_name_ambiguity"
            reason = "Multiple plausible football-club candidates share the club name; confirm the right entity."
    elif status == "candidate_no_coordinates":
        if women_flag:
            bucket = "manual_review_gender_team_mismatch"
            reason = "Candidate may point to a women's team instead of the intended club."
        elif non_club_flag:
            bucket = "retry_search_wrong_entity"
            reason = "Top candidate looks like a non-club or wrong-sport entity; rerun with better search aliases."
        elif football_like:
            bucket = "coordinate_backfill_needed"
            reason = "Club match looks plausible, but Wikidata did not provide usable coordinates."
        else:
            bucket = "manual_review_low_context_candidate"
            reason = "Candidate lacks coordinates and does not clearly identify a football club."
    elif status == "candidate_coords_need_review":
        if non_club_flag:
            bucket = "retry_search_wrong_entity"
            reason = "Top candidate looks like a place/non-club entity rather than a football club."
        else:
            bucket = "manual_review_club_vs_place"
            reason = "Coordinates came from the club entity or a place-like candidate, so the source needs checking."
    elif status == "no_wikidata_candidates_found":
        bucket = "manual_search_alias_retry"
        reason = "No search candidate was found; try stripped, ASCII-folded, or FC-suffixed aliases."
    else:
        bucket = "hard_manual_match"
        reason = "Low-score or clearly ambiguous search result requires direct manual selection."

    if players >= 8 and bucket not in {"batch_approve_stadium_coords"}:
        priority = "high"
    elif players >= 4:
        priority = "medium"
    else:
        priority = "low"

    return bucket, reason, priority, second_label, second_score or score_gap


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage Step 6 club geolocation review queue.")
    parser.add_argument(
        "--indir",
        default="data/processed/club_geolocation_working",
        help="Folder containing Step 6 working CSVs.",
    )
    parser.add_argument(
        "--outdir",
        default="data/processed/club_geolocation_working",
        help="Folder where triage CSVs should be written.",
    )
    args = parser.parse_args()

    indir = Path(args.indir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    review_path = indir / "club_geocoding_review_queue.csv"
    candidate_path = indir / "club_wikidata_candidates_step6.csv"
    if not review_path.exists():
        raise FileNotFoundError(f"Missing review queue: {review_path}")
    if not candidate_path.exists():
        raise FileNotFoundError(f"Missing candidates file: {candidate_path}")

    review_rows = read_csv(review_path)
    candidate_rows = read_csv(candidate_path)

    candidates_by_club: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        candidates_by_club[row.get("club_id", "")].append(row)
    for club_id in list(candidates_by_club):
        candidates_by_club[club_id] = sort_candidates(candidates_by_club[club_id])

    triage_rows: List[Dict[str, str]] = []
    for row in review_rows:
        club_id = row.get("club_id", "")
        club_candidates = candidates_by_club.get(club_id, [])
        second_label = ""
        second_score = ""
        score_gap = ""
        if len(club_candidates) > 1:
            top_score = numeric_int(club_candidates[0].get("candidate_score", ""))
            second_score_value = numeric_int(club_candidates[1].get("candidate_score", ""))
            second_label = club_candidates[1].get("wikidata_label", "")
            second_score = str(second_score_value)
            score_gap = str(top_score - second_score_value)

        bucket, reason, priority, _, _ = triage_row(row, club_candidates)
        enriched = dict(row)
        enriched["triage_bucket"] = bucket
        enriched["triage_reason"] = reason
        enriched["review_priority"] = priority
        enriched["exact_name_match"] = "TRUE" if exact_normalized_match(row.get("club_name", ""), row.get("wikidata_label", "")) else "FALSE"
        enriched["club_name_token_count"] = str(token_count(row.get("club_name", "")))
        enriched["women_entity_flag"] = "TRUE" if is_women_entity(row) else "FALSE"
        enriched["non_club_entity_flag"] = "TRUE" if is_non_club_entity(row) else "FALSE"
        enriched["likely_football_club_flag"] = "TRUE" if looks_like_football_club(row) else "FALSE"
        enriched["second_candidate_label"] = second_label
        enriched["second_candidate_score"] = second_score
        enriched["score_gap_to_second"] = score_gap
        enriched["manual_search_hint"] = build_manual_search_hint(row.get("club_name", ""))
        triage_rows.append(enriched)

    triage_rows = sorted(
        triage_rows,
        key=lambda row: (
            row.get("triage_bucket", ""),
            {"high": 0, "medium": 1, "low": 2}.get(row.get("review_priority", "low"), 3),
            -numeric_int(row.get("player_count", "")),
            row.get("club_name", ""),
        ),
    )

    base_fields = list(review_rows[0].keys()) if review_rows else []
    triage_fields = base_fields + [
        "triage_bucket",
        "triage_reason",
        "review_priority",
        "exact_name_match",
        "club_name_token_count",
        "women_entity_flag",
        "non_club_entity_flag",
        "likely_football_club_flag",
        "second_candidate_label",
        "second_candidate_score",
        "score_gap_to_second",
        "manual_search_hint",
    ]

    write_csv(outdir / "club_geocoding_review_triage.csv", triage_rows, triage_fields)

    bucket_counts = Counter(row["triage_bucket"] for row in triage_rows)
    priority_counts = Counter(row["review_priority"] for row in triage_rows)
    summary_rows = [{"metric": "review_rows", "value": str(len(triage_rows))}]
    for bucket, count in sorted(bucket_counts.items()):
        summary_rows.append({"metric": f"triage_bucket__{bucket}", "value": str(count)})
    for priority, count in sorted(priority_counts.items()):
        summary_rows.append({"metric": f"priority__{priority}", "value": str(count)})

    write_csv(outdir / "club_geocoding_review_triage_summary.csv", summary_rows, ["metric", "value"])

    print(f"Wrote triage rows: {outdir / 'club_geocoding_review_triage.csv'}")
    print(f"Wrote triage summary: {outdir / 'club_geocoding_review_triage_summary.csv'}")
    for row in summary_rows:
        print(f"{row['metric']}: {row['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
