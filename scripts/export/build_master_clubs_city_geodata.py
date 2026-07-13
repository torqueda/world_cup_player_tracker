#!/usr/bin/env python3
"""
Build a club-level city geodata export for the master workbook.

This resolves the 456-club versus 393-city mismatch by joining each canonical
club row back to its deduplicated city geocode via `club_id`.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from workbook_rows import read_sheet_rows


FULL_OUTPUT_FIELDS = [
    "club_id",
    "wikidata_id",
    "club_name",
    "club_name_ascii",
    "league",
    "country",
    "city",
    "stadium",
    "city_lat",
    "city_lon",
    "city_source_url",
    "city_geo_source",
    "city_match_confidence",
    "manual_review_flag",
    "notes",
    "city_key",
    "city_review_notes",
]

IMPORT_OUTPUT_FIELDS = [
    "club_id",
    "club_name",
    "club_name_ascii",
    "league",
    "country",
    "city",
    "stadium",
    "city_lat",
    "city_lon",
    "city_source_url",
    "city_geo_source",
    "city_match_confidence",
    "city_key",
    "city_review_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--master-workbook",
        default="data/master/world_cup_2026_player_map_master.xlsx",
        help="Current master workbook.",
    )
    parser.add_argument(
        "--master-sheet",
        default="clubs",
        help="Workbook sheet to read as the club master base.",
    )
    parser.add_argument(
        "--club-baseline",
        default="data/processed/club_geolocation_baseline/clubs_geocoded_corrected.csv",
        help="Canonical club baseline.",
    )
    parser.add_argument(
        "--city-workfile",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_workfile.csv",
        help="Final city geocoding workfile.",
    )
    parser.add_argument(
        "--full-output",
        default="data/processed/master_exports/clubs_sheet_city_geodata_full.csv",
        help="Full master-ready club export with city geodata.",
    )
    parser.add_argument(
        "--import-output",
        default="data/processed/master_exports/clubs_sheet_city_geodata_import.csv",
        help="Slim import/export file for easy workbook updating.",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_pipe_list(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def normalize_bool(value: object) -> str:
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    text = str(value or "").strip()
    if not text:
        return "FALSE"
    return text.upper()


def clean_master_note(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("Wikidata/league/city/stadium pending Step 5b/Step 6.", "").strip()
    text = text.replace("  ", " ").strip(" ;")
    return text


def main() -> None:
    args = parse_args()

    master_rows = read_sheet_rows(args.master_workbook, args.master_sheet)
    baseline_rows = read_csv_rows(Path(args.club_baseline))
    city_rows = read_csv_rows(Path(args.city_workfile))

    baseline_by_id = {row["club_id"]: row for row in baseline_rows}
    city_by_club_id: dict[str, dict[str, str]] = {}
    for city_row in city_rows:
        for club_id in split_pipe_list(city_row.get("club_ids", "")):
            city_by_club_id[club_id] = city_row

    full_output: list[dict[str, str]] = []
    import_output: list[dict[str, str]] = []
    missing_baseline: list[str] = []
    missing_city: list[str] = []

    for master_row in master_rows:
        club_id = str(master_row.get("club_id", "")).strip()
        baseline_row = baseline_by_id.get(club_id)
        if not baseline_row:
            missing_baseline.append(club_id)
            continue

        city_row = city_by_club_id.get(club_id)
        if not city_row:
            missing_city.append(club_id)
            continue

        full_row = {
            "club_id": club_id,
            "wikidata_id": str(master_row.get("wikidata_id", "") or ""),
            "club_name": baseline_row["club_name"],
            "club_name_ascii": baseline_row["club_name_ascii"],
            "league": baseline_row["league"],
            "country": baseline_row["country"],
            "city": baseline_row["city"],
            "stadium": baseline_row["stadium"],
            "city_lat": city_row.get("latitude", ""),
            "city_lon": city_row.get("longitude", ""),
            "city_source_url": city_row.get("geocode_source_url", ""),
            "city_geo_source": city_row.get("geocode_source", ""),
            "city_match_confidence": city_row.get("match_confidence", ""),
            "manual_review_flag": normalize_bool(master_row.get("manual_review_flag", False)),
            "notes": clean_master_note(master_row.get("notes", "")),
            "city_key": city_row.get("city_key", ""),
            "city_review_notes": city_row.get("review_notes", ""),
        }
        full_output.append(full_row)
        import_output.append({field: full_row[field] for field in IMPORT_OUTPUT_FIELDS})

    if missing_baseline:
        raise SystemExit(f"Missing baseline rows for {len(missing_baseline)} club_ids: {missing_baseline[:10]}")
    if missing_city:
        raise SystemExit(f"Missing city geocode rows for {len(missing_city)} club_ids: {missing_city[:10]}")

    full_output_path = Path(args.full_output)
    import_output_path = Path(args.import_output)
    full_output_path.parent.mkdir(parents=True, exist_ok=True)

    with full_output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FULL_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(full_output)

    with import_output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=IMPORT_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(import_output)

    print(f"Read {len(master_rows)} master club rows from {args.master_workbook}:{args.master_sheet}")
    print(f"Matched {len(full_output)} clubs to canonical city geodata")
    print(f"Wrote full output to {full_output_path}")
    print(f"Wrote import output to {import_output_path}")


if __name__ == "__main__":
    main()
