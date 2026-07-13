#!/usr/bin/env python3
"""
Prepare collection-ready city geocoding files from the city geocoding workfile.

Outputs:
- a prioritized queue for manual/external geocoding
- a minimal results template to fill in with confirmed city coordinates
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_workfile.csv",
        help="City geocoding workfile.",
    )
    parser.add_argument(
        "--queue-output",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_collection_queue.csv",
        help="Prioritized city geocoding queue.",
    )
    parser.add_argument(
        "--results-template-output",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_results_template.csv",
        help="Blank city geocoding results template.",
    )
    return parser.parse_args()


STATUS_PRIORITY = {
    "ready_for_geocoding_with_local_hints": 0,
    "ready_for_geocoding_no_local_hints": 1,
    "ready_for_geocoding_with_untrusted_hints": 2,
}


def priority_score(row: dict[str, str]) -> tuple[int, int, str, str]:
    status_rank = STATUS_PRIORITY.get(row["review_status"], 99)
    source_row_count = -int(row["source_row_count"])
    return (status_rank, source_row_count, row["country"], row["city"])


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    queue_output_path = Path(args.queue_output)
    results_template_path = Path(args.results_template_output)
    queue_output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    queue_rows = []
    template_rows = []
    for row in sorted(rows, key=priority_score):
        queue_rows.append(
            {
                "city_key": row["city_key"],
                "country": row["country"],
                "city": row["city"],
                "preferred_city_query": row["preferred_city_query"],
                "review_status": row["review_status"],
                "review_priority": row["review_priority"],
                "source_row_count": row["source_row_count"],
                "club_names": row["club_names"],
                "stadiums": row["stadiums"],
                "primary_stadium_context_query": row["primary_stadium_context_query"],
                "primary_club_context_query": row["primary_club_context_query"],
                "trusted_stadium_hint_coord_count": row["trusted_stadium_hint_coord_count"],
                "existing_club_coord_centroid_lat": row["existing_club_coord_centroid_lat"],
                "existing_club_coord_centroid_lon": row["existing_club_coord_centroid_lon"],
                "existing_coordinate_basis_values": row["existing_coordinate_basis_values"],
                "existing_coordinate_source_urls": row["existing_coordinate_source_urls"],
                "data_quality_flags": row["data_quality_flags"],
                "review_notes": row["review_notes"],
            }
        )
        template_rows.append(
            {
                "city_key": row["city_key"],
                "country": row["country"],
                "city": row["city"],
                "preferred_city_query": row["preferred_city_query"],
                "latitude": "",
                "longitude": "",
                "geocode_source": "",
                "geocode_source_url": "",
                "match_confidence": "",
                "review_notes": "",
            }
        )

    queue_fields = [
        "city_key",
        "country",
        "city",
        "preferred_city_query",
        "review_status",
        "review_priority",
        "source_row_count",
        "club_names",
        "stadiums",
        "primary_stadium_context_query",
        "primary_club_context_query",
        "trusted_stadium_hint_coord_count",
        "existing_club_coord_centroid_lat",
        "existing_club_coord_centroid_lon",
        "existing_coordinate_basis_values",
        "existing_coordinate_source_urls",
        "data_quality_flags",
        "review_notes",
    ]
    template_fields = [
        "city_key",
        "country",
        "city",
        "preferred_city_query",
        "latitude",
        "longitude",
        "geocode_source",
        "geocode_source_url",
        "match_confidence",
        "review_notes",
    ]

    with queue_output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=queue_fields)
        writer.writeheader()
        writer.writerows(queue_rows)

    with results_template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=template_fields)
        writer.writeheader()
        writer.writerows(template_rows)

    print(f"Prepared {len(queue_rows)} queue rows at {queue_output_path}")
    print(f"Prepared {len(template_rows)} template rows at {results_template_path}")


if __name__ == "__main__":
    main()
