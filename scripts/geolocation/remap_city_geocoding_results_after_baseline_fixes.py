#!/usr/bin/env python3
"""
Remap preserved city geocoding results onto corrected canonical city-country keys.

This is intended for small baseline cleanups after manual geocoding has already been
completed, so corrected coordinates can be preserved without regenerating the entire
results template from scratch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import unicodedata
from pathlib import Path


REMAPS = [
    {
        "old_country": "Saudi Arabia",
        "old_city": "Abu Dhabi",
        "new_country": "United Arab Emirates",
        "new_city": "Abu Dhabi",
    },
    {
        "old_country": "Denmark",
        "old_city": "Silkeborg Municipality",
        "new_country": "Denmark",
        "new_city": "Silkeborg",
    },
    {
        "old_country": "Germany",
        "old_city": "Gelsenkirchen-Nord",
        "new_country": "Germany",
        "new_city": "Gelsenkirchen",
    },
    {
        "old_country": "Germany",
        "old_city": "Treptow-Köpenick",
        "new_country": "Germany",
        "new_city": "Berlin",
    },
    {
        "old_country": "Norway",
        "old_city": "Reknes",
        "new_country": "Norway",
        "new_city": "Molde",
    },
    {
        "old_country": "Germany",
        "old_city": "Frankfurt",
        "new_country": "Germany",
        "new_city": "Frankfurt am Main",
        "field_updates": {
            "latitude": "50.11552",
            "longitude": "8.68417",
            "geocode_source": "geonames_searchJSON",
            "geocode_source_url": "https://www.geonames.org/2925533",
            "match_confidence": "high",
            "review_notes": (
                "GeoNames exact match retained for Frankfurt am Main, Germany. "
                "Canonical city label updated from Frankfurt to Frankfurt am Main."
            ),
        },
    },
    {
        "old_country": "Mexico",
        "old_city": "Monterrey",
        "new_country": "Mexico",
        "new_city": "Guadalupe, Nuevo León",
        "field_updates": {
            "latitude": "25.67678",
            "longitude": "-100.25646",
            "geocode_source": "geonames_searchJSON",
            "geocode_source_url": "https://www.geonames.org/4005492",
            "match_confidence": "high",
            "review_notes": (
                "GeoNames exact city match retained for Guadalupe, Nuevo León, Mexico, "
                "which is the home city of Estadio BBVA."
            ),
        },
    },
    {
        "old_country": "Portugal",
        "old_city": "Freguesia de Vila Boa",
        "new_country": "Portugal",
        "new_city": "Barcelos",
        "field_updates": {
            "review_notes": "Manual city correction retained for Barcelos, Portugal.",
        },
    },
    {
        "old_country": "Portugal",
        "old_city": "Real, Dume e Semelhe",
        "new_country": "Portugal",
        "new_city": "Braga",
        "field_updates": {
            "review_notes": "Manual city correction retained for Braga, Portugal.",
        },
    },
    {
        "old_country": "Sweden",
        "old_city": "Malmö Municipality",
        "new_country": "Sweden",
        "new_city": "Malmö",
        "field_updates": {
            "review_notes": "Manual city correction retained for Malmö, Sweden.",
        },
    },
    {
        "old_country": "Sweden",
        "old_city": "Sölvesborg Municipality",
        "new_country": "Sweden",
        "new_city": "Hällevik",
        "field_updates": {
            "review_notes": "Manual city correction retained for Hällevik, Sweden.",
        },
    },
    {
        "old_country": "Switzerland",
        "old_city": "Canton of Geneva",
        "new_country": "Switzerland",
        "new_city": "Lancy",
        "field_updates": {
            "review_notes": "Manual city correction retained for Lancy, Switzerland.",
        },
    },
    {
        "old_country": "United Arab Emirates",
        "old_city": "Emirate of Fujairah",
        "new_country": "United Arab Emirates",
        "new_city": "Fujairah",
        "field_updates": {
            "review_notes": "Manual city correction retained for Fujairah, United Arab Emirates.",
        },
    },
    {
        "old_country": "United States",
        "old_city": "Texas",
        "new_country": "United States",
        "new_city": "Frisco",
        "field_updates": {
            "review_notes": "Manual city correction retained for Frisco, Texas, United States.",
        },
    },
    {
        "old_country": "South Korea",
        "old_city": "Dongan-gu",
        "new_country": "South Korea",
        "new_city": "Seoul",
        "field_updates": {
            "latitude": "37.566",
            "longitude": "126.9784",
            "geocode_source": "geonames_searchJSON",
            "geocode_source_url": "https://www.geonames.org/1835848",
            "match_confidence": "high",
            "review_notes": (
                "FC Seoul official site lists Seoul World Cup Stadium in Seoul as the home venue; "
                "city coordinates updated to Seoul, South Korea."
            ),
        },
    },
]

NOTE_OVERRIDES_BY_CITY = {
    ("Denmark", "Silkeborg"): "Manual city correction retained for Silkeborg, Denmark.",
    ("Germany", "Gelsenkirchen"): "Manual city correction retained for Gelsenkirchen, Germany.",
    ("Germany", "Berlin"): "Manual city correction retained for Berlin, Germany.",
    ("Norway", "Molde"): "Manual city correction retained for Molde, Norway.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_results_template.csv",
        help="Existing geocoding results template to remap in place.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_results_template.csv",
        help="Output path for the remapped template.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "blank"


def build_city_key(country: str, city: str) -> str:
    digest = hashlib.sha1(f"{country}||{city}".encode("utf-8")).hexdigest()[:8]
    return f"{slugify(country)}__{slugify(city)}__{digest}"


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def append_note(existing: str, note: str) -> str:
    existing = existing.strip()
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def build_key_map(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    mapping: dict[str, dict[str, object]] = {}
    for item in items:
        mapping[build_city_key(str(item["old_country"]), str(item["old_city"]))] = item
    return mapping


def build_note_override_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for (country, city), note in NOTE_OVERRIDES_BY_CITY.items():
        mapping[build_city_key(country, city)] = note
    return mapping


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    rows, fieldnames = read_rows(input_path)

    remap_by_old_key = build_key_map(REMAPS)
    note_override_by_key = build_note_override_map()

    rows_by_key = {row["city_key"]: row for row in rows if row.get("city_key")}
    output_rows: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    remapped = 0
    dropped_duplicates = 0

    for row in rows:
        row = dict(row)
        old_key = row.get("city_key", "")
        target = remap_by_old_key.get(old_key)
        if target:
            new_country = str(target["new_country"])
            new_city = str(target["new_city"])
            new_key = build_city_key(new_country, new_city)
            existing_target = rows_by_key.get(new_key)
            if existing_target and new_key != old_key:
                dropped_duplicates += 1
                continue

            row["country"] = new_country
            row["city"] = new_city
            row["preferred_city_query"] = f"{new_city}, {new_country}"
            row["city_key"] = new_key
            for field, value in dict(target.get("field_updates", {})).items():
                row[field] = str(value)
            if "field_updates" not in target or "review_notes" not in dict(target.get("field_updates", {})):
                row["review_notes"] = append_note(
                    row.get("review_notes", ""),
                    f"Canonical city-country label updated to '{new_city}, {new_country}'.",
                )
            remapped += 1

        new_key = row.get("city_key", "")
        if new_key in note_override_by_key:
            row["review_notes"] = note_override_by_key[new_key]
        if new_key in seen_keys:
            continue
        seen_keys.add(new_key)
        output_rows.append(row)

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Loaded {len(rows)} results rows from {input_path}")
    print(f"Remapped {remapped} rows onto corrected canonical city-country keys")
    print(f"Dropped {dropped_duplicates} obsolete duplicate rows")
    print(f"Wrote {len(output_rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
