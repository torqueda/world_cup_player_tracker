#!/usr/bin/env python3
"""
Merge collected city geocoding results back into the city geocoding workfile.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workfile",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_workfile.csv",
        help="City geocoding workfile to update.",
    )
    parser.add_argument(
        "--results",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_results_template.csv",
        help="Collected city geocoding results CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workfile_path = Path(args.workfile)
    results_path = Path(args.results)

    with workfile_path.open("r", encoding="utf-8-sig", newline="") as handle:
        work_rows = list(csv.DictReader(handle))
        fieldnames = list(work_rows[0].keys()) if work_rows else []

    with results_path.open("r", encoding="utf-8-sig", newline="") as handle:
        result_rows = list(csv.DictReader(handle))

    results_by_key = {row["city_key"]: row for row in result_rows if row.get("city_key")}

    applied = 0
    for row in work_rows:
        result = results_by_key.get(row["city_key"])
        if not result:
            continue
        if not result.get("latitude") or not result.get("longitude"):
            continue

        row["latitude"] = result["latitude"]
        row["longitude"] = result["longitude"]
        row["geocode_source"] = result.get("geocode_source", "")
        row["geocode_source_url"] = result.get("geocode_source_url", "")
        row["match_confidence"] = result.get("match_confidence", "")
        row["review_notes"] = result.get("review_notes", row.get("review_notes", ""))
        applied += 1

    with workfile_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(work_rows)

    print(f"Applied {applied} city geocoding results to {workfile_path}")


if __name__ == "__main__":
    main()
