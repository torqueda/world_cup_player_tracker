#!/usr/bin/env python3
"""
Build a city geocoding workfile from the canonical club city-country lookup.

The output is designed for reliable downstream geocoding review:
- exact canonical city/country values from the lookup
- club/stadium context for disambiguation
- legacy local query strings from prior geolocation work
- existing club/stadium coordinate hints kept separate from final city geocodes
- blank final latitude/longitude fields for confirmed city-level coordinates
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--city-lookup",
        default="data/processed/club_geolocation_baseline/club_city_country_lookup.csv",
        help="Deduplicated city-country lookup CSV.",
    )
    parser.add_argument(
        "--club-baseline",
        default="data/processed/club_geolocation_baseline/clubs_geocoded_reconciled.csv",
        help="Club baseline with legacy coordinate metadata.",
    )
    parser.add_argument(
        "--legacy-hybrid-input",
        default="data/processed/club_geolocation_hybrid/hybrid_geolocation_unresolved_input.csv",
        help="Legacy hybrid geolocation input with city/stadium/club query strings.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_workfile.csv",
        help="Output city geocoding workfile CSV.",
    )
    return parser.parse_args()


def read_csv_with_fallback(path: Path, encodings: list[str]) -> tuple[list[dict[str, str]], str]:
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle)), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise RuntimeError(f"Could not decode {path}") from last_error


def split_pipe_list(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def maybe_float(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_quality_flags(row: dict[str, str], unique_stadium_count: int) -> list[str]:
    flags: list[str] = []
    suspicious_fields = [row["country"], row["city"], row["club_names"], row["stadiums"]]
    if any("_" in value or "�" in value for value in suspicious_fields):
        flags.append("possible_text_encoding_issue")
    if int(row["source_row_count"]) > 1:
        flags.append("multiple_clubs_same_city_country")
    if unique_stadium_count > 1:
        flags.append("multiple_stadium_contexts")
    return flags


def main() -> None:
    args = parse_args()
    city_lookup_path = Path(args.city_lookup)
    club_baseline_path = Path(args.club_baseline)
    legacy_hybrid_path = Path(args.legacy_hybrid_input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    city_rows, city_encoding = read_csv_with_fallback(city_lookup_path, ["utf-8-sig", "utf-8"])
    club_rows, club_encoding = read_csv_with_fallback(
        club_baseline_path, ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    )
    hybrid_rows, hybrid_encoding = read_csv_with_fallback(
        legacy_hybrid_path, ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    )

    club_by_id = {row["club_id"]: row for row in club_rows}
    hybrid_by_id = {row["club_id"]: row for row in hybrid_rows}

    output_rows: list[dict[str, str]] = []
    hint_count = 0

    for row in city_rows:
        club_ids = split_pipe_list(row["club_ids"])
        club_names = split_pipe_list(row["club_names"])
        stadiums = split_pipe_list(row["stadiums"])

        coord_points: list[tuple[float, float]] = []
        trusted_coord_points: list[tuple[float, float]] = []
        coord_basis_values: list[str] = []
        coord_sources: list[str] = []
        coord_source_urls: list[str] = []
        untrusted_coord_basis_values: list[str] = []
        legacy_geonames_queries: list[str] = []
        legacy_stadium_queries: list[str] = []
        legacy_club_queries: list[str] = []

        for club_id in club_ids:
            baseline_row = club_by_id.get(club_id)
            hybrid_row = hybrid_by_id.get(club_id)

            lat = lon = None
            if baseline_row:
                lat = maybe_float(baseline_row.get("club_lat", ""))
                lon = maybe_float(baseline_row.get("club_lon", ""))
                if baseline_row.get("coordinate_basis"):
                    coord_basis_values.append(baseline_row["coordinate_basis"])
                if baseline_row.get("geo_source"):
                    coord_sources.append(baseline_row["geo_source"])
                if baseline_row.get("geo_source_url"):
                    coord_source_urls.append(baseline_row["geo_source_url"])

            if (lat is None or lon is None) and hybrid_row:
                lat = maybe_float(hybrid_row.get("current_club_lat", ""))
                lon = maybe_float(hybrid_row.get("current_club_lon", ""))

            if lat is not None and lon is not None:
                coord_points.append((lat, lon))
                if baseline_row and baseline_row.get("coordinate_basis") == "wikidata_home_venue_P115_to_stadium_P625":
                    trusted_coord_points.append((lat, lon))
                elif baseline_row and baseline_row.get("coordinate_basis"):
                    untrusted_coord_basis_values.append(baseline_row["coordinate_basis"])

            if hybrid_row:
                if hybrid_row.get("geonames_city_query"):
                    legacy_geonames_queries.append(hybrid_row["geonames_city_query"])
                if hybrid_row.get("search_query_stadium"):
                    legacy_stadium_queries.append(hybrid_row["search_query_stadium"])
                if hybrid_row.get("search_query_club"):
                    legacy_club_queries.append(hybrid_row["search_query_club"])

        if coord_points:
            hint_count += 1

        unique_stadium_count = len(sorted_unique(stadiums))
        data_quality_flags = build_quality_flags(row, unique_stadium_count)
        if coord_points and not trusted_coord_points:
            data_quality_flags.append("only_untrusted_local_coordinate_hints")
        if len(trusted_coord_points) >= 2:
            trusted_lat_range = max(lat for lat, _ in trusted_coord_points) - min(lat for lat, _ in trusted_coord_points)
            trusted_lon_range = max(lon for _, lon in trusted_coord_points) - min(lon for _, lon in trusted_coord_points)
            if trusted_lat_range > 1 or trusted_lon_range > 1:
                data_quality_flags.append("trusted_local_hints_have_large_spread")

        if "possible_text_encoding_issue" in data_quality_flags:
            review_priority = "high"
            review_status = "needs_text_review_before_geocoding"
            review_notes = "Canonical text appears suspicious; verify city/country spelling before external geocoding."
        elif trusted_coord_points:
            review_priority = "medium"
            review_status = "ready_for_geocoding_with_local_hints"
            review_notes = (
                "Trusted stadium-based coordinates are available as local hints only; "
                "confirm true city coordinates from a city-level source."
            )
        elif coord_points:
            review_priority = "high"
            review_status = "ready_for_geocoding_with_untrusted_hints"
            review_notes = (
                "Only untrusted local coordinate hints were found; use them as context, "
                "but do not treat them as a city centroid."
            )
        else:
            review_priority = "medium"
            review_status = "ready_for_geocoding_no_local_hints"
            review_notes = "No local coordinate hints were found; geocode directly from the city-country query."

        centroid_lat = f"{mean(lat for lat, _ in trusted_coord_points):.8f}" if trusted_coord_points else ""
        centroid_lon = f"{mean(lon for _, lon in trusted_coord_points):.8f}" if trusted_coord_points else ""
        primary_stadium = stadiums[0] if stadiums else ""
        primary_club = club_names[0] if club_names else ""

        output_rows.append(
            {
                "city_key": row["city_key"],
                "country": row["country"],
                "city": row["city"],
                "preferred_city_query": f"{row['city']}, {row['country']}",
                "source_row_count": row["source_row_count"],
                "distinct_club_id_count": row["distinct_club_id_count"],
                "distinct_club_name_count": row["distinct_club_name_count"],
                "club_ids": row["club_ids"],
                "club_names": row["club_names"],
                "leagues": row["leagues"],
                "stadiums": row["stadiums"],
                "primary_stadium_context_query": (
                    f"{primary_stadium}, {row['city']}, {row['country']}" if primary_stadium else ""
                ),
                "primary_club_context_query": (
                    f"{primary_club}, {row['city']}, {row['country']}" if primary_club else ""
                ),
                "legacy_geonames_city_queries": " | ".join(sorted_unique(legacy_geonames_queries)),
                "legacy_stadium_queries": " | ".join(sorted_unique(legacy_stadium_queries)),
                "legacy_club_queries": " | ".join(sorted_unique(legacy_club_queries)),
                "existing_club_coord_count": str(len(coord_points)),
                "trusted_stadium_hint_coord_count": str(len(trusted_coord_points)),
                "existing_club_coord_centroid_lat": centroid_lat,
                "existing_club_coord_centroid_lon": centroid_lon,
                "existing_coordinate_basis_values": " | ".join(sorted_unique(coord_basis_values)),
                "untrusted_coordinate_basis_values": " | ".join(sorted_unique(untrusted_coord_basis_values)),
                "existing_coordinate_sources": " | ".join(sorted_unique(coord_sources)),
                "existing_coordinate_source_urls": " | ".join(sorted_unique(coord_source_urls)),
                "data_quality_flags": " | ".join(data_quality_flags),
                "review_priority": review_priority,
                "latitude": "",
                "longitude": "",
                "geocode_source": "",
                "geocode_source_url": "",
                "match_confidence": "",
                "review_status": review_status,
                "review_notes": review_notes,
                "input_city_lookup_encoding": city_encoding,
                "input_club_baseline_encoding": club_encoding,
                "input_legacy_hybrid_encoding": hybrid_encoding,
            }
        )

    fieldnames = [
        "city_key",
        "country",
        "city",
        "preferred_city_query",
        "source_row_count",
        "distinct_club_id_count",
        "distinct_club_name_count",
        "club_ids",
        "club_names",
        "leagues",
        "stadiums",
        "primary_stadium_context_query",
        "primary_club_context_query",
        "legacy_geonames_city_queries",
        "legacy_stadium_queries",
        "legacy_club_queries",
        "existing_club_coord_count",
        "trusted_stadium_hint_coord_count",
        "existing_club_coord_centroid_lat",
        "existing_club_coord_centroid_lon",
        "existing_coordinate_basis_values",
        "untrusted_coordinate_basis_values",
        "existing_coordinate_sources",
        "existing_coordinate_source_urls",
        "data_quality_flags",
        "review_priority",
        "latitude",
        "longitude",
        "geocode_source",
        "geocode_source_url",
        "match_confidence",
        "review_status",
        "review_notes",
        "input_city_lookup_encoding",
        "input_club_baseline_encoding",
        "input_legacy_hybrid_encoding",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Read {len(city_rows)} city rows from {city_lookup_path}")
    print(f"Wrote {len(output_rows)} city geocoding rows to {output_path}")
    print(f"Rows with local coordinate hints: {hint_count}")


if __name__ == "__main__":
    main()
