#!/usr/bin/env python3
"""
Build a deduplicated city-country lookup table from the canonical club baseline.

This script intentionally treats the current club baseline values as authoritative.
It does not normalize or rewrite the club data; it only groups distinct city-country
pairs and carries club context to support downstream geocoding and manual review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/club_geolocation_baseline/clubs_geocoded_corrected.csv",
        help="Canonical club baseline CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/club_geolocation_baseline/club_city_country_lookup.csv",
        help="Output city-country lookup CSV.",
    )
    return parser.parse_args()


def read_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    encodings = ["utf-8-sig", "utf-8", "mac_roman", "latin-1"]
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle)), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise RuntimeError(f"Could not decode {path}") from last_error


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "blank"


def build_city_key(country: str, city: str) -> str:
    digest = hashlib.sha1(f"{country}||{city}".encode("utf-8")).hexdigest()[:8]
    return f"{slugify(country)}__{slugify(city)}__{digest}"


def sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows, encoding_used = read_rows(input_path)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        grouped[(row["country"], row["city"])].append(row)

    output_rows: list[dict[str, str]] = []
    for (country, city), members in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        club_ids = [row["club_id"] for row in members]
        club_names = [row["club_name"] for row in members]
        leagues = [row["league"] for row in members]
        stadiums = [row["stadium"] for row in members]

        output_rows.append(
            {
                "city_key": build_city_key(country, city),
                "country": country,
                "city": city,
                "source_row_count": str(len(members)),
                "distinct_club_id_count": str(len(sorted_unique(club_ids))),
                "distinct_club_name_count": str(len(sorted_unique(club_names))),
                "club_ids": " | ".join(sorted_unique(club_ids)),
                "club_names": " | ".join(sorted_unique(club_names)),
                "leagues": " | ".join(sorted_unique(leagues)),
                "stadiums": " | ".join(sorted_unique(stadiums)),
                "source_encoding_detected": encoding_used,
            }
        )

    fieldnames = [
        "city_key",
        "country",
        "city",
        "source_row_count",
        "distinct_club_id_count",
        "distinct_club_name_count",
        "club_ids",
        "club_names",
        "leagues",
        "stadiums",
        "source_encoding_detected",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Read {len(rows)} club rows from {input_path}")
    print(f"Wrote {len(output_rows)} unique city-country rows to {output_path}")
    print(f"Input encoding used: {encoding_used}")


if __name__ == "__main__":
    main()
