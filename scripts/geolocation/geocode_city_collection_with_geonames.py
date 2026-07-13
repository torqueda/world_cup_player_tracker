#!/usr/bin/env python3
"""
Geocode the city collection queue against GeoNames using one city-level source.

This script keeps the final coordinate source consistent:
- final latitude/longitude always come from GeoNames
- local club/stadium centroid hints are used only to disambiguate GeoNames results
- output is plug-compatible with apply_city_geocoding_results.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import ssl
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GEONAMES_SEARCH_API_HTTPS = "https://api.geonames.org/searchJSON"
GEONAMES_SEARCH_API_HTTP = "http://api.geonames.org/searchJSON"
DEFAULT_USER_AGENT = "world-cup-player-tracker-city-geocoder/0.1"
RESULT_FIELDS = [
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

COUNTRY_TO_ISO2 = {
    "Algeria": "DZ",
    "Argentina": "AR",
    "Armenia": "AM",
    "Australia": "AU",
    "Austria": "AT",
    "Azerbaijan": "AZ",
    "Belgium": "BE",
    "Brazil": "BR",
    "Bulgaria": "BG",
    "Canada": "CA",
    "Chile": "CL",
    "Colombia": "CO",
    "Costa Rica": "CR",
    "Croatia": "HR",
    "Cyprus": "CY",
    "Czech Republic": "CZ",
    "Denmark": "DK",
    "Ecuador": "EC",
    "Egypt": "EG",
    "England": "GB",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Ghana": "GH",
    "Greece": "GR",
    "Haiti": "HT",
    "Honduras": "HN",
    "Hungary": "HU",
    "Iran": "IR",
    "Iraq": "IQ",
    "Ireland": "IE",
    "Israel": "IL",
    "Italy": "IT",
    "Japan": "JP",
    "Jordan": "JO",
    "Kazakhstan": "KZ",
    "Malaysia": "MY",
    "Mexico": "MX",
    "Monaco": "MC",
    "Morocco": "MA",
    "Netherlands": "NL",
    "New Zealand": "NZ",
    "Norway": "NO",
    "Panama": "PA",
    "Paraguay": "PY",
    "People's Republic of China": "CN",
    "Poland": "PL",
    "Portugal": "PT",
    "Qatar": "QA",
    "Romania": "RO",
    "Russia": "RU",
    "Saudi Arabia": "SA",
    "Scotland": "GB",
    "Serbia": "RS",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "South Africa": "ZA",
    "South Korea": "KR",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Syria": "SY",
    "Thailand": "TH",
    "Tunisia": "TN",
    "Turkey": "TR",
    "United Arab Emirates": "AE",
    "United States": "US",
    "Uruguay": "UY",
    "Uzbekistan": "UZ",
    "Venezuela": "VE",
    "Wales": "GB",
}

FEATURE_CODE_SCORE = {
    "PPLC": 12,
    "PPLA": 10,
    "PPLA2": 9,
    "PPLA3": 8,
    "PPLA4": 7,
    "PPL": 6,
    "PPLX": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_collection_queue.csv",
        help="City geocoding collection queue CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/club_geolocation_baseline/club_city_geocoding_results_template.csv",
        help="Filled city geocoding results CSV.",
    )
    parser.add_argument(
        "--geonames-username",
        default="",
        help="GeoNames username. Falls back to GEONAMES_USERNAME env var.",
    )
    parser.add_argument(
        "--contact",
        default="",
        help="Optional contact string appended to the HTTP user agent.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.75,
        help="Delay between GeoNames requests.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit for testing. 0 means all rows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned query modes without calling GeoNames.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore any existing output file and rebuild from scratch.",
    )
    parser.add_argument(
        "--transport",
        choices=["auto", "https", "http"],
        default="auto",
        help="GeoNames transport. auto tries HTTPS first and falls back to HTTP on TLS failure.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def maybe_float(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_place(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    chars: list[str] = []
    for ch in text.lower():
        chars.append(ch if ch.isalnum() else " ")
    return " ".join("".join(chars).split())


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def geonames_params(
    *,
    query_key: str,
    query_value: str,
    country_code: str,
    username: str,
) -> dict[str, str]:
    return {
        query_key: query_value,
        "country": country_code,
        "featureClass": "P",
        "maxRows": "10",
        "style": "FULL",
        "lang": "local",
        "charset": "UTF8",
        "username": username,
    }


def fetch_geonames_candidates(
    *,
    user_agent: str,
    base_url: str,
    query_key: str,
    query_value: str,
    country_code: str,
    username: str,
    delay_seconds: float,
) -> list[dict[str, Any]]:
    request = Request(
        f"{base_url}?{urlencode(geonames_params(
            query_key=query_key,
            query_value=query_value,
            country_code=country_code,
            username=username,
        ))}",
        headers={"User-Agent": user_agent},
    )
    try:
        with urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = None

        status = (parsed or {}).get("status") if isinstance(parsed, dict) else None
        if isinstance(status, dict):
            message = str(status.get("message", "")).strip()
            value = status.get("value")
            detail = f"GeoNames error {value}: {message}" if value is not None else f"GeoNames error: {message}"
            raise RuntimeError(detail) from exc
        raise
    if delay_seconds:
        time.sleep(delay_seconds)
    return list((data or {}).get("geonames") or [])


def resolve_base_urls(transport: str) -> list[str]:
    if transport == "https":
        return [GEONAMES_SEARCH_API_HTTPS]
    if transport == "http":
        return [GEONAMES_SEARCH_API_HTTP]
    return [GEONAMES_SEARCH_API_HTTPS, GEONAMES_SEARCH_API_HTTP]


def fetch_with_transport_fallback(
    *,
    user_agent: str,
    transport: str,
    query_key: str,
    query_value: str,
    country_code: str,
    username: str,
    delay_seconds: float,
) -> tuple[list[dict[str, Any]], str]:
    last_error: Exception | None = None
    for base_url in resolve_base_urls(transport):
        try:
            return (
                fetch_geonames_candidates(
                    user_agent=user_agent,
                    base_url=base_url,
                    query_key=query_key,
                    query_value=query_value,
                    country_code=country_code,
                    username=username,
                    delay_seconds=delay_seconds,
                ),
                base_url,
            )
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError) and base_url == GEONAMES_SEARCH_API_HTTPS:
                last_error = exc
                continue
            last_error = exc
            raise
    assert last_error is not None
    raise last_error


def score_candidate(row: dict[str, str], candidate: dict[str, Any]) -> dict[str, Any]:
    target_norm = normalize_place(row["city"])
    candidate_names = [
        str(candidate.get("name", "") or ""),
        str(candidate.get("toponymName", "") or ""),
    ]
    candidate_norms = [normalize_place(name) for name in candidate_names if name]
    exact_name_match = target_norm in candidate_norms
    partial_name_match = any(target_norm in name or name in target_norm for name in candidate_norms if name)

    score = 0.0
    if exact_name_match:
        score += 120.0
    elif partial_name_match:
        score += 35.0

    feature_code = str(candidate.get("fcode", "") or "")
    score += FEATURE_CODE_SCORE.get(feature_code, 0)

    population = int(candidate.get("population") or 0)
    if population > 0:
        score += min(18.0, math.log10(population + 1) * 3)

    distance_km: float | None = None
    centroid_lat = maybe_float(row.get("existing_club_coord_centroid_lat", ""))
    centroid_lon = maybe_float(row.get("existing_club_coord_centroid_lon", ""))
    candidate_lat = maybe_float(str(candidate.get("lat", "")))
    candidate_lon = maybe_float(str(candidate.get("lng", "")))
    if None not in {centroid_lat, centroid_lon, candidate_lat, candidate_lon}:
        distance_km = haversine_km(centroid_lat, centroid_lon, candidate_lat, candidate_lon)
        if distance_km <= 15:
            score += 45.0
        elif distance_km <= 40:
            score += 35.0
        elif distance_km <= 75:
            score += 25.0
        elif distance_km <= 150:
            score += 10.0
        elif distance_km > 300:
            score -= 35.0

    return {
        "candidate": candidate,
        "score": score,
        "exact_name_match": exact_name_match,
        "partial_name_match": partial_name_match,
        "distance_km": distance_km,
        "population": population,
        "feature_code": feature_code,
    }


def choose_best_candidate(
    row: dict[str, str],
    candidates: list[dict[str, Any]],
    *,
    query_mode: str,
    transport_used: str,
) -> tuple[str, str, str, str, str, str]:
    if not candidates:
        return "", "", "", "", "low", "GeoNames returned no populated-place matches for this city-country query."

    scored = [score_candidate(row, candidate) for candidate in candidates]
    scored.sort(
        key=lambda item: (
            -item["score"],
            item["distance_km"] if item["distance_km"] is not None else float("inf"),
            -item["population"],
        )
    )

    best = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None
    margin = best["score"] - runner_up["score"] if runner_up else 999.0
    candidate = best["candidate"]
    latitude = str(candidate.get("lat", "") or "")
    longitude = str(candidate.get("lng", "") or "")
    geoname_id = str(candidate.get("geonameId", "") or "")
    source_url = f"https://www.geonames.org/{geoname_id}" if geoname_id else ""

    confidence = "medium"
    if not best["exact_name_match"]:
        confidence = "low"
    elif best["distance_km"] is not None and best["distance_km"] > 200:
        confidence = "low"
    elif query_mode != "name_equals":
        confidence = "medium"
    elif margin < 15:
        confidence = "medium"
    elif best["distance_km"] is None or best["distance_km"] <= 75:
        confidence = "high"

    review_bits = [
        f"GeoNames {query_mode} match",
        f"selected '{candidate.get('toponymName') or candidate.get('name')}'",
    ]
    admin_name = str(candidate.get("adminName1", "") or "")
    if admin_name:
        review_bits.append(f"admin '{admin_name}'")
    if best["feature_code"]:
        review_bits.append(f"feature {best['feature_code']}")
    if best["population"]:
        review_bits.append(f"population {best['population']}")
    if best["distance_km"] is not None:
        review_bits.append(f"{best['distance_km']:.1f} km from trusted local centroid")
    if runner_up:
        review_bits.append(f"top-vs-next score margin {margin:.1f}")
    if confidence != "high":
        review_bits.append("spot-check recommended before promoting to final club coordinates")

    if transport_used == "http":
        review_bits.append("HTTP fallback was used because the GeoNames HTTPS certificate failed verification")

    return latitude, longitude, "geonames_searchJSON", source_url, confidence, "; ".join(review_bits) + "."


def blank_result(row: dict[str, str], review_notes: str) -> dict[str, str]:
    return {
        "city_key": row["city_key"],
        "country": row["country"],
        "city": row["city"],
        "preferred_city_query": row["preferred_city_query"],
        "latitude": "",
        "longitude": "",
        "geocode_source": "",
        "geocode_source_url": "",
        "match_confidence": "low",
        "review_notes": review_notes,
    }


def build_result_row(row: dict[str, str], latitude: str, longitude: str, source: str, source_url: str, confidence: str, review_notes: str) -> dict[str, str]:
    return {
        "city_key": row["city_key"],
        "country": row["country"],
        "city": row["city"],
        "preferred_city_query": row["preferred_city_query"],
        "latitude": latitude,
        "longitude": longitude,
        "geocode_source": source,
        "geocode_source_url": source_url,
        "match_confidence": confidence,
        "review_notes": review_notes,
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_csv(input_path)
    if args.limit > 0:
        rows = rows[: args.limit]

    if args.dry_run:
        for row in rows[: min(len(rows), 10)]:
            country_code = COUNTRY_TO_ISO2.get(row["country"], "MISSING")
            print(f"{row['preferred_city_query']} -> country={country_code} -> query order: name_equals, name, ascii_name")
        print(f"Dry run prepared {len(rows)} rows from {input_path}")
        return

    username = args.geonames_username or os.environ.get("GEONAMES_USERNAME", "")
    if not username:
        raise SystemExit("GeoNames username required. Pass --geonames-username or set GEONAMES_USERNAME.")

    existing_results_by_key: dict[str, dict[str, str]] = {}
    if not args.no_resume and output_path.exists():
        existing_rows = read_csv(output_path)
        existing_results_by_key = {
            row["city_key"]: row
            for row in existing_rows
            if row.get("city_key") and row.get("latitude") and row.get("longitude")
        }

    user_agent = f"{DEFAULT_USER_AGENT} ({args.contact or 'no-contact-provided'})"

    output_rows: list[dict[str, str]] = []
    confidence_counts = {"high": 0, "medium": 0, "low": 0}

    for index, row in enumerate(rows, start=1):
        city_key = row["city_key"]
        if city_key in existing_results_by_key:
            result = existing_results_by_key[city_key]
            output_rows.append(result)
            confidence_counts[result.get("match_confidence", "low")] = confidence_counts.get(
                result.get("match_confidence", "low"), 0
            ) + 1
            print(f"[{index}/{len(rows)}] Reused existing result for {row['preferred_city_query']}", flush=True)
            continue

        print(f"[{index}/{len(rows)}] Geocoding {row['preferred_city_query']}...", flush=True)
        country_code = COUNTRY_TO_ISO2.get(row["country"], "")
        if not country_code:
            result = blank_result(row, f"No ISO-3166 mapping is configured for country label '{row['country']}'.")
            output_rows.append(result)
            confidence_counts["low"] += 1
            continue

        city = row["city"]
        ascii_city = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode("ascii")
        try:
            candidates, transport_url = fetch_with_transport_fallback(
                user_agent=user_agent,
                transport=args.transport,
                query_key="name_equals",
                query_value=city,
                country_code=country_code,
                username=username,
                delay_seconds=args.request_delay_seconds,
            )
            query_mode = "name_equals"
            if not candidates:
                candidates, transport_url = fetch_with_transport_fallback(
                    user_agent=user_agent,
                    transport=args.transport,
                    query_key="name",
                    query_value=city,
                    country_code=country_code,
                    username=username,
                    delay_seconds=args.request_delay_seconds,
                )
                query_mode = "name"
            if not candidates and ascii_city and ascii_city != city:
                candidates, transport_url = fetch_with_transport_fallback(
                    user_agent=user_agent,
                    transport=args.transport,
                    query_key="name",
                    query_value=ascii_city,
                    country_code=country_code,
                    username=username,
                    delay_seconds=args.request_delay_seconds,
                )
                query_mode = "ascii_name"

            latitude, longitude, source, source_url, confidence, review_notes = choose_best_candidate(
                row,
                candidates,
                query_mode=query_mode,
                transport_used="http" if transport_url.startswith("http://") else "https",
            )
            result = build_result_row(row, latitude, longitude, source, source_url, confidence, review_notes)
        except Exception as exc:
            result = blank_result(row, f"GeoNames request failed: {exc}")

        output_rows.append(result)
        confidence_counts[result.get("match_confidence", "low")] = confidence_counts.get(
            result.get("match_confidence", "low"), 0
        ) + 1
        write_csv(output_path, output_rows)

    write_csv(output_path, output_rows)
    print(f"Wrote {len(output_rows)} city geocoding results to {output_path}")
    print(
        "Match confidence summary: "
        f"high={confidence_counts.get('high', 0)}, "
        f"medium={confidence_counts.get('medium', 0)}, "
        f"low={confidence_counts.get('low', 0)}"
    )


if __name__ == "__main__":
    main()
