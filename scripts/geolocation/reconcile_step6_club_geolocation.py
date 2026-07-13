#!/usr/bin/env python3
"""
Reconcile Step 6 club geolocation outputs into a single clean table.

This script combines:
1. The manually reviewed Step 6 triage rows.
2. The Step 6 working rows that were auto-approved with
   match_status = auto_candidate_high_stadium_coords.

It intentionally keeps a compact, downstream-friendly schema and drops the
triage/debug columns that were only useful during candidate vetting.

Outputs:
- clubs_geocoded_reconciled.csv
- clubs_geocoded_reconciled_summary.csv
- clubs_step5_only_not_in_step6_audit.csv

The audit file surfaces Step 5 club rows that are absent from the Step 6
snapshot so they can be resolved deliberately instead of disappearing quietly.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


OUTPUT_FIELDS = [
    "club_id",
    "wikidata_id",
    "club_name",
    "club_name_ascii",
    "league",
    "country",
    "city",
    "stadium",
    "club_lat",
    "club_lon",
    "geo_source_url",
    "club_source_url",
    "geo_source",
    "coordinate_basis",
    "wikipedia_url",
    "wikidata_url",
    "match_status",
    "review_status",
    "review_source_file",
    "player_count",
    "notes",
    "manual_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step5-clubs",
        default="data/processed/club_normalization_final/clubs_final_for_master.csv",
        help="Final Step 5 clubs file used to audit clubs missing from the Step 6 snapshot.",
    )
    parser.add_argument(
        "--step6-working",
        default="data/processed/club_geolocation_working/clubs_step6_working.csv",
        help="Step 6 working file that includes auto-approved rows.",
    )
    parser.add_argument(
        "--step6-triage",
        default="data/processed/club_geolocation_working/club_geocoding_review_triage.csv",
        help="Step 6 triage file containing manually reviewed rows.",
    )
    parser.add_argument(
        "--outdir",
        default="data/processed/club_geolocation_working",
        help="Directory where reconciled outputs should be written.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path}")


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def choose(*values: str) -> str:
    for value in values:
        if str(value or "").strip():
            return str(value).strip()
    return ""


def as_output_row(row: Dict[str, str], review_status: str, review_source_file: str) -> Dict[str, str]:
    return {
        "club_id": row.get("club_id", ""),
        "wikidata_id": row.get("wikidata_id", ""),
        "club_name": row.get("club_name", ""),
        "club_name_ascii": row.get("club_name_ascii", ""),
        "league": row.get("league", ""),
        "country": row.get("country", ""),
        "city": row.get("city", ""),
        "stadium": row.get("stadium", ""),
        "club_lat": choose(row.get("proposed_club_lat", ""), row.get("club_lat", "")),
        "club_lon": choose(row.get("proposed_club_lon", ""), row.get("club_lon", "")),
        "geo_source_url": row.get("geo_source_url", ""),
        "club_source_url": row.get("club_source_url", ""),
        "geo_source": choose(row.get("geo_source", ""), "wikidata_step6"),
        "coordinate_basis": row.get("coordinate_basis", ""),
        "wikipedia_url": row.get("wikipedia_url", ""),
        "wikidata_url": choose(row.get("wikidata_url", ""), row.get("club_source_url", "")),
        "match_status": row.get("match_status", ""),
        "review_status": review_status,
        "review_source_file": review_source_file,
        "player_count": row.get("player_count", ""),
        "notes": row.get("notes", ""),
        "manual_notes": choose(row.get("manual_notes", ""), row.get("triage_reason", "")),
    }


def sort_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(rows, key=lambda row: (row.get("club_name", "").lower(), row.get("club_id", "")))


def build_missing_step6_audit(
    step5_rows: List[Dict[str, str]],
    step6_rows: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    step6_ids = {row.get("club_id", "") for row in step6_rows}
    audit_rows = []
    for row in step5_rows:
        club_id = row.get("club_id", "")
        if club_id and club_id not in step6_ids:
            audit_rows.append(
                {
                    "club_id": club_id,
                    "club_name": row.get("club_name", ""),
                    "club_name_ascii": row.get("club_name_ascii", ""),
                    "country": row.get("country", ""),
                    "league": row.get("league", ""),
                    "city": row.get("city", ""),
                    "stadium": row.get("stadium", ""),
                    "notes": row.get("notes", ""),
                }
            )
    return sort_rows(audit_rows)


def build_summary_rows(
    reconciled_rows: List[Dict[str, str]],
    missing_step6_audit: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    summary = []
    summary.append({"metric": "reconciled_rows", "value": str(len(reconciled_rows))})
    summary.append(
        {
            "metric": "review_status__manual_club_metadata_reviewed_triage",
            "value": str(
                sum(1 for row in reconciled_rows if row["review_status"] == "manual_club_metadata_reviewed_triage")
            ),
        }
    )
    summary.append(
        {
            "metric": "review_status__auto_candidate_high_stadium_coords",
            "value": str(
                sum(1 for row in reconciled_rows if row["review_status"] == "auto_candidate_high_stadium_coords")
            ),
        }
    )
    summary.append({"metric": "step5_only_rows_not_in_step6_snapshot", "value": str(len(missing_step6_audit))})

    for field in ("league", "country", "city", "stadium", "club_lat", "club_lon", "wikidata_id", "wikipedia_url"):
        summary.append(
            {
                "metric": f"nonblank__{field}",
                "value": str(sum(1 for row in reconciled_rows if row.get(field, "").strip())),
            }
        )

    match_counts = Counter(row.get("match_status", "") for row in reconciled_rows)
    for match_status, count in sorted(match_counts.items()):
        summary.append({"metric": f"match_status__{match_status}", "value": str(count)})

    return summary


def main() -> None:
    args = parse_args()
    step5_path = Path(args.step5_clubs)
    step6_working_path = Path(args.step6_working)
    step6_triage_path = Path(args.step6_triage)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    step5_rows = read_csv(step5_path)
    step6_working_rows = read_csv(step6_working_path)
    step6_triage_rows = read_csv(step6_triage_path)

    triage_ids = {row.get("club_id", "") for row in step6_triage_rows}
    auto_rows = [
        row
        for row in step6_working_rows
        if row.get("club_id", "") not in triage_ids
        and row.get("match_status", "") == "auto_candidate_high_stadium_coords"
    ]

    manual_rows_out = [
        as_output_row(row, "manual_club_metadata_reviewed_triage", step6_triage_path.name)
        for row in step6_triage_rows
    ]
    auto_rows_out = [
        as_output_row(row, "auto_candidate_high_stadium_coords", step6_working_path.name)
        for row in auto_rows
    ]

    reconciled_by_id: Dict[str, Dict[str, str]] = {}
    for row in manual_rows_out + auto_rows_out:
        club_id = row.get("club_id", "")
        if not club_id:
            continue
        reconciled_by_id[club_id] = row

    reconciled_rows = sort_rows(reconciled_by_id.values())
    missing_step6_audit = build_missing_step6_audit(step5_rows, step6_working_rows)
    summary_rows = build_summary_rows(reconciled_rows, missing_step6_audit)

    write_csv(outdir / "clubs_geocoded_reconciled.csv", reconciled_rows, OUTPUT_FIELDS)
    write_csv(outdir / "clubs_geocoded_reconciled_summary.csv", summary_rows, ["metric", "value"])
    write_csv(
        outdir / "clubs_step5_only_not_in_step6_audit.csv",
        missing_step6_audit,
        ["club_id", "club_name", "club_name_ascii", "country", "league", "city", "stadium", "notes"],
    )


if __name__ == "__main__":
    main()
