#!/usr/bin/env python3
"""
Prepare and optionally run a hybrid geolocation resolution pass for Step 6 clubs.

Resolution order:
1. Wikipedia API page coordinates
2. OSM Overpass stadium/venue lookup
3. GeoNames city fallback
4. Flag rows that still require official-source fallback/manual review

This script is non-destructive. It writes new artifacts and never edits source files.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, TextIO, Tuple
from urllib.parse import unquote, urlparse

import requests


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
OVERPASS_API = "https://overpass-api.de/api/interpreter"
GEONAMES_SEARCH_API = "https://api.geonames.org/searchJSON"

DEFAULT_USER_AGENT = "world-cup-player-tracker-hybrid-geolocation/0.1"

PREPARED_FIELDNAMES = [
    "club_id",
    "club_name",
    "club_name_ascii",
    "league",
    "country",
    "city",
    "stadium",
    "wikipedia_url",
    "wikidata_url",
    "match_status",
    "review_status",
    "player_count",
    "current_club_lat",
    "current_club_lon",
    "wikipedia_page_title",
    "search_query_stadium",
    "search_query_club",
    "geonames_city_query",
    "resolution_priority",
]

RESOLUTION_FIELDNAMES = PREPARED_FIELDNAMES + [
    "wikipedia_lat",
    "wikipedia_lon",
    "wikipedia_source_url",
    "overpass_lat",
    "overpass_lon",
    "overpass_source_url",
    "geonames_lat",
    "geonames_lon",
    "geonames_source_url",
    "recommended_lat",
    "recommended_lon",
    "recommended_source",
    "recommended_source_url",
    "recommended_coordinate_basis",
    "conflict_distance_km",
    "resolver_status",
    "official_source_fallback_needed",
    "manual_review_reason",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/processed/club_geolocation_working/clubs_geocoded_reconciled.csv",
        help="Reconciled Step 6 clubs file.",
    )
    parser.add_argument(
        "--outdir",
        default="data/processed/club_geolocation_hybrid",
        help="Directory for hybrid-resolution outputs.",
    )
    parser.add_argument(
        "--mode",
        choices=["prepare", "resolve"],
        default="prepare",
        help="prepare writes the unresolved input queue only; resolve also calls external services.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit for testing. 0 means no limit.",
    )
    parser.add_argument(
        "--contact",
        default="",
        help="Contact string for API user-agent etiquette.",
    )
    parser.add_argument(
        "--geonames-username",
        default="",
        help="GeoNames username for city fallback requests.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.6,
        help="Delay between live requests in resolve mode.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume from an existing partial resolution file; start a fresh resolve run.",
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


def open_incremental_csv_writer(
    path: Path,
    fieldnames: List[str],
    append: bool,
) -> Tuple[TextIO, csv.DictWriter]:
    file_exists = path.exists() and path.stat().st_size > 0
    mode = "a" if append and file_exists else "w"
    handle = path.open(mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    if mode == "w":
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())
    return handle, writer


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def ascii_fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def wikipedia_title_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path or ""
    if "/wiki/" not in path:
        return ""
    return unquote(path.split("/wiki/", 1)[1]).replace("_", " ")


def build_stadium_query(row: Dict[str, str]) -> str:
    parts = [row.get("stadium", ""), row.get("city", ""), row.get("country", "")]
    return normalize_whitespace(", ".join(part for part in parts if part))


def build_club_query(row: Dict[str, str]) -> str:
    parts = [row.get("club_name", ""), row.get("city", ""), row.get("country", "")]
    return normalize_whitespace(", ".join(part for part in parts if part))


def resolution_priority(row: Dict[str, str]) -> str:
    if not row.get("club_lat", "").strip() or not row.get("club_lon", "").strip():
        return "missing_coordinates"
    if row.get("match_status") in {"candidate_coords_need_review", "needs_manual_match_review", "no_wikidata_candidates_found"}:
        return "high_review"
    if row.get("review_status") == "manual_club_metadata_reviewed_triage":
        return "manual_triage_followup"
    return "spotcheck"


def needs_hybrid_resolution(row: Dict[str, str]) -> bool:
    if not row.get("club_lat", "").strip() or not row.get("club_lon", "").strip():
        return True
    if not row.get("city", "").strip():
        return True
    return row.get("review_status") == "manual_club_metadata_reviewed_triage"


def prepare_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    prepared = []
    for row in rows:
        if not needs_hybrid_resolution(row):
            continue
        prepared.append(
            {
                "club_id": row.get("club_id", ""),
                "club_name": row.get("club_name", ""),
                "club_name_ascii": row.get("club_name_ascii", ""),
                "league": row.get("league", ""),
                "country": row.get("country", ""),
                "city": row.get("city", ""),
                "stadium": row.get("stadium", ""),
                "wikipedia_url": row.get("wikipedia_url", ""),
                "wikidata_url": row.get("wikidata_url", ""),
                "match_status": row.get("match_status", ""),
                "review_status": row.get("review_status", ""),
                "player_count": row.get("player_count", ""),
                "current_club_lat": row.get("club_lat", ""),
                "current_club_lon": row.get("club_lon", ""),
                "wikipedia_page_title": wikipedia_title_from_url(row.get("wikipedia_url", "")),
                "search_query_stadium": build_stadium_query(row),
                "search_query_club": build_club_query(row),
                "geonames_city_query": normalize_whitespace(", ".join(part for part in [row.get("city", ""), row.get("country", "")] if part)),
                "resolution_priority": resolution_priority(row),
            }
        )
    return prepared


def safe_get_json(session: requests.Session, url: str, params: Dict[str, str], delay_seconds: float) -> Optional[Dict]:
    response = session.get(url, params=params, timeout=45)
    response.raise_for_status()
    if delay_seconds:
        time.sleep(delay_seconds)
    return response.json()


def fetch_wikipedia_coords(
    session: requests.Session,
    page_title: str,
    delay_seconds: float,
) -> Tuple[str, str, str]:
    if not page_title:
        return "", "", ""
    data = safe_get_json(
        session,
        WIKIPEDIA_API,
        {
            "action": "query",
            "prop": "coordinates",
            "titles": page_title,
            "format": "json",
            "colimit": "1",
        },
        delay_seconds,
    )
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    for page in pages.values():
        coords = page.get("coordinates") or []
        if coords:
            lat = str(coords[0].get("lat", ""))
            lon = str(coords[0].get("lon", ""))
            return lat, lon, f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
    return "", "", ""


def overpass_query_for_stadium(stadium: str, city: str, country: str) -> str:
    terms = [term for term in [stadium, city, country] if term]
    escaped = re.sub(r'"', '\\"', " ".join(terms))
    return f"""
[out:json][timeout:25];
(
  nwr["name"="{escaped}"];
  nwr["name"~"{escaped}", i]["leisure"="stadium"];
  nwr["name"~"{escaped}", i]["building"="stadium"];
  nwr["name"~"{escaped}", i]["sport"="soccer"];
);
out center 3;
""".strip()


def fetch_overpass_coords(
    session: requests.Session,
    stadium: str,
    city: str,
    country: str,
    delay_seconds: float,
) -> Tuple[str, str, str]:
    if not stadium:
        return "", "", ""
    response = session.get(
        OVERPASS_API,
        params={"data": overpass_query_for_stadium(stadium, city, country)},
        timeout=60,
    )
    response.raise_for_status()
    if delay_seconds:
        time.sleep(delay_seconds)
    data = response.json()
    elements = data.get("elements") or []
    for element in elements:
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            center = element.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")
        if lat is not None and lon is not None:
            osm_type = element.get("type", "")
            osm_id = element.get("id", "")
            return str(lat), str(lon), f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    return "", "", ""


def fetch_geonames_city_coords(
    session: requests.Session,
    city: str,
    country: str,
    username: str,
    delay_seconds: float,
) -> Tuple[str, str, str]:
    if not username or not city:
        return "", "", ""
    data = safe_get_json(
        session,
        GEONAMES_SEARCH_API,
        {
            "q": city,
            "country": "",
            "maxRows": "1",
            "style": "FULL",
            "username": username,
        },
        delay_seconds,
    )
    hits = (data or {}).get("geonames") or []
    if not hits:
        return "", "", ""
    top = hits[0]
    lat = str(top.get("lat", ""))
    lon = str(top.get("lng", ""))
    geoname_id = str(top.get("geonameId", ""))
    return lat, lon, f"https://www.geonames.org/{geoname_id}"


def to_float(value: str) -> Optional[float]:
    try:
        if str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def haversine_km(lat1: str, lon1: str, lat2: str, lon2: str) -> str:
    a1 = to_float(lat1)
    b1 = to_float(lon1)
    a2 = to_float(lat2)
    b2 = to_float(lon2)
    if None in {a1, b1, a2, b2}:
        return ""
    r = 6371.0
    dlat = math.radians(a2 - a1)
    dlon = math.radians(b2 - b1)
    aa = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a1)) * math.cos(math.radians(a2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(aa), math.sqrt(1 - aa))
    return f"{r * c:.3f}"


def build_resolved_row(
    row: Dict[str, str],
    wikipedia_lat: str,
    wikipedia_lon: str,
    wikipedia_source: str,
    overpass_lat: str,
    overpass_lon: str,
    overpass_source: str,
    geonames_lat: str,
    geonames_lon: str,
    geonames_source: str,
    recommended_lat: str,
    recommended_lon: str,
    recommended_source: str,
    recommended_source_url: str,
    recommended_coordinate_basis: str,
    conflict_distance_km: str,
    resolver_status: str,
    official_source_fallback_needed: str,
    manual_review_reason: str,
) -> Dict[str, str]:
    return {
        **row,
        "wikipedia_lat": wikipedia_lat,
        "wikipedia_lon": wikipedia_lon,
        "wikipedia_source_url": wikipedia_source,
        "overpass_lat": overpass_lat,
        "overpass_lon": overpass_lon,
        "overpass_source_url": overpass_source,
        "geonames_lat": geonames_lat,
        "geonames_lon": geonames_lon,
        "geonames_source_url": geonames_source,
        "recommended_lat": recommended_lat,
        "recommended_lon": recommended_lon,
        "recommended_source": recommended_source,
        "recommended_source_url": recommended_source_url,
        "recommended_coordinate_basis": recommended_coordinate_basis,
        "conflict_distance_km": conflict_distance_km,
        "resolver_status": resolver_status,
        "official_source_fallback_needed": official_source_fallback_needed,
        "manual_review_reason": manual_review_reason,
    }


def resolve_prepared_rows(
    prepared_rows: List[Dict[str, str]],
    contact: str,
    geonames_username: str,
    delay_seconds: float,
    incremental_output_path: Path,
    resume: bool,
) -> Tuple[List[Dict[str, str]], bool]:
    session = requests.Session()
    session.headers.update({"User-Agent": f"{DEFAULT_USER_AGENT} ({contact or 'no-contact-provided'})"})

    resolved_rows: List[Dict[str, str]] = []
    existing_by_id: Dict[str, Dict[str, str]] = {}
    if resume and incremental_output_path.exists():
        existing_rows = read_csv(incremental_output_path)
        existing_by_id = {row["club_id"]: row for row in existing_rows if row.get("club_id", "")}
        resolved_rows.extend(existing_rows)

    pending_rows = [row for row in prepared_rows if row.get("club_id", "") not in existing_by_id]
    if existing_by_id:
        print(
            f"Resuming from existing partial output: {len(existing_by_id)} rows already saved, "
            f"{len(pending_rows)} rows remaining.",
            flush=True,
        )
    else:
        print(f"Starting resolve run for {len(prepared_rows)} rows.", flush=True)

    handle, writer = open_incremental_csv_writer(
        incremental_output_path,
        RESOLUTION_FIELDNAMES,
        append=resume,
    )
    interrupted = False

    try:
        for index, row in enumerate(pending_rows, start=len(existing_by_id) + 1):
            club_name = row.get("club_name", "")
            club_id = row.get("club_id", "")
            print(f"[{index}/{len(prepared_rows)}] Resolving {club_name} ({club_id})...", flush=True)
            row_started_at = time.time()
            wikipedia_lat = wikipedia_lon = wikipedia_source = ""
            overpass_lat = overpass_lon = overpass_source = ""
            geonames_lat = geonames_lon = geonames_source = ""
            recommended_lat = recommended_lon = recommended_source = ""
            recommended_source_url = recommended_coordinate_basis = ""
            conflict_distance_km = ""
            resolver_status = "unresolved"
            official_source_fallback_needed = "FALSE"
            manual_review_reason = ""

            try:
                wikipedia_lat, wikipedia_lon, wikipedia_source = fetch_wikipedia_coords(
                    session,
                    row.get("wikipedia_page_title", ""),
                    delay_seconds,
                )
            except Exception as exc:
                manual_review_reason = f"Wikipedia API error: {exc}"

            try:
                overpass_lat, overpass_lon, overpass_source = fetch_overpass_coords(
                    session,
                    row.get("stadium", ""),
                    row.get("city", ""),
                    row.get("country", ""),
                    delay_seconds,
                )
            except Exception as exc:
                manual_review_reason = "; ".join(part for part in [manual_review_reason, f"Overpass error: {exc}"] if part)

            try:
                geonames_lat, geonames_lon, geonames_source = fetch_geonames_city_coords(
                    session,
                    row.get("city", ""),
                    row.get("country", ""),
                    geonames_username,
                    delay_seconds,
                )
            except Exception as exc:
                manual_review_reason = "; ".join(part for part in [manual_review_reason, f"GeoNames error: {exc}"] if part)

            if overpass_lat and overpass_lon:
                recommended_lat, recommended_lon = overpass_lat, overpass_lon
                recommended_source = "osm_overpass_stadium"
                recommended_source_url = overpass_source
                recommended_coordinate_basis = "stadium_osm"
                resolver_status = "resolved"
            elif wikipedia_lat and wikipedia_lon:
                recommended_lat, recommended_lon = wikipedia_lat, wikipedia_lon
                recommended_source = "wikipedia_page_coordinates"
                recommended_source_url = wikipedia_source
                recommended_coordinate_basis = "wikipedia_page"
                resolver_status = "resolved"
            elif geonames_lat and geonames_lon:
                recommended_lat, recommended_lon = geonames_lat, geonames_lon
                recommended_source = "geonames_city_fallback"
                recommended_source_url = geonames_source
                recommended_coordinate_basis = "city_geonames"
                resolver_status = "resolved_city_fallback"
            else:
                official_source_fallback_needed = "TRUE"
                if not manual_review_reason:
                    manual_review_reason = "No hybrid source returned usable coordinates."

            if wikipedia_lat and wikipedia_lon and overpass_lat and overpass_lon:
                conflict_distance_km = haversine_km(wikipedia_lat, wikipedia_lon, overpass_lat, overpass_lon)

            resolved_row = build_resolved_row(
                row,
                wikipedia_lat,
                wikipedia_lon,
                wikipedia_source,
                overpass_lat,
                overpass_lon,
                overpass_source,
                geonames_lat,
                geonames_lon,
                geonames_source,
                recommended_lat,
                recommended_lon,
                recommended_source,
                recommended_source_url,
                recommended_coordinate_basis,
                conflict_distance_km,
                resolver_status,
                official_source_fallback_needed,
                manual_review_reason,
            )
            writer.writerow(resolved_row)
            handle.flush()
            os.fsync(handle.fileno())
            resolved_rows.append(resolved_row)

            elapsed = time.time() - row_started_at
            print(
                f"[{index}/{len(prepared_rows)}] Saved {club_name} -> {resolver_status}"
                f"{' via ' + recommended_source if recommended_source else ''} ({elapsed:.1f}s)",
                flush=True,
            )
    except KeyboardInterrupt:
        interrupted = True
        print(
            f"\nInterrupted. Partial results were saved to {incremental_output_path}. "
            f"Rerun the same command to resume.",
            flush=True,
        )
    finally:
        handle.close()

    return resolved_rows, interrupted


def build_summary_rows(prepared_rows: List[Dict[str, str]], resolved_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    rows = [
        {"metric": "prepared_rows", "value": str(len(prepared_rows))},
    ]
    priority_counts = Counter(row["resolution_priority"] for row in prepared_rows)
    for priority, count in sorted(priority_counts.items()):
        rows.append({"metric": f"resolution_priority__{priority}", "value": str(count)})

    if resolved_rows:
        status_counts = Counter(row["resolver_status"] for row in resolved_rows)
        for status, count in sorted(status_counts.items()):
            rows.append({"metric": f"resolver_status__{status}", "value": str(count)})
        rows.append(
            {
                "metric": "official_source_fallback_needed_rows",
                "value": str(sum(1 for row in resolved_rows if row["official_source_fallback_needed"] == "TRUE")),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    source_rows = read_csv(input_path)
    prepared_rows = prepare_rows(source_rows)
    if args.limit > 0:
        prepared_rows = prepared_rows[: args.limit]

    write_csv(outdir / "hybrid_geolocation_unresolved_input.csv", prepared_rows, PREPARED_FIELDNAMES)

    resolved_rows: List[Dict[str, str]] = []
    interrupted = False
    if args.mode == "resolve":
        resolved_rows, interrupted = resolve_prepared_rows(
            prepared_rows,
            contact=args.contact,
            geonames_username=args.geonames_username,
            delay_seconds=args.request_delay_seconds,
            incremental_output_path=outdir / "hybrid_geolocation_resolution_candidates.csv",
            resume=not args.no_resume,
        )

    summary_rows = build_summary_rows(prepared_rows, resolved_rows)
    if args.mode == "resolve":
        summary_rows.append({"metric": "run_interrupted", "value": "TRUE" if interrupted else "FALSE"})
        summary_rows.append({"metric": "resolved_rows_saved", "value": str(len(resolved_rows))})
    write_csv(outdir / "hybrid_geolocation_summary.csv", summary_rows, ["metric", "value"])


if __name__ == "__main__":
    main()
