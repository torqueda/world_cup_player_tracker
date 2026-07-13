#!/usr/bin/env python3
"""
Export the master workbook to app-ready JSON files.

The workbook is the preferred source of truth. A club-geodata overlay remains
available as a fallback for older workbook copies that do not yet contain the
city-level geocoding fields in the `clubs` sheet.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from workbook_rows import list_sheet_names, read_sheet_rows

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--master-workbook",
        default=str(REPO_ROOT / "data/master/world_cup_2026_player_map_master.xlsx"),
        help="Current master workbook.",
    )
    parser.add_argument(
        "--club-geodata-overlay",
        default=str(REPO_ROOT / "data/processed/master_exports/clubs_sheet_city_geodata_full.csv"),
        help="Optional club-level geodata overlay CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "data/processed/app_exports"),
        help="Directory for JSON exports.",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "blank"


def ascii_fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.encode("ascii", "ignore").decode("ascii")


def repo_relative(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def build_city_key(country: str, city: str) -> str:
    digest = hashlib.sha1(f"{country}||{city}".encode("utf-8")).hexdigest()[:8]
    return f"{slugify(country)}__{slugify(city)}__{digest}"


BOOL_STRINGS = {
    "TRUE": True,
    "FALSE": False,
    "True": True,
    "False": False,
}

FLOAT_FIELDS = {
    "birth_lat",
    "birth_lon",
    "city_lat",
    "city_lon",
    "latitude",
    "longitude",
}

INT_FIELDS = {
    "height_cm",
    "shirt_number",
    "source_row_count",
    "distinct_club_id_count",
    "distinct_club_name_count",
    "existing_club_coord_count",
    "trusted_stadium_hint_coord_count",
    "club_count",
    "squad_size",
    "replacement_count",
}


def normalize_scalar(key: str, value: Any) -> Any:
    if value in ("", None):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in BOOL_STRINGS:
            return BOOL_STRINGS[stripped]
        if key in FLOAT_FIELDS:
            try:
                return float(stripped)
            except ValueError:
                return stripped
        if key in INT_FIELDS:
            try:
                return int(stripped)
            except ValueError:
                try:
                    number = float(stripped)
                except ValueError:
                    return stripped
                return int(number) if number.is_integer() else number
        return stripped
    return value


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        output[key] = normalize_scalar(key, value)
    return output


def build_cities_from_clubs(clubs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    club_ids_by_city: defaultdict[str, list[str]] = defaultdict(list)

    for club in clubs:
        if club.get("city_lat") is None or club.get("city_lon") is None:
            # Not yet geocoded (e.g. clubs added for late roster replacements);
            # keep the club row but leave it off the map's city surface.
            continue
        country = str(club.get("country") or "")
        city = str(club.get("city") or "")
        city_key = str(club.get("city_key") or build_city_key(country, city))
        club_ids_by_city[city_key].append(str(club.get("club_id") or ""))

        grouped.setdefault(
            city_key,
            {
                "city_key": city_key,
                "country": country,
                "city": city,
                "city_ascii": ascii_fold(city),
                "city_lat": club.get("city_lat"),
                "city_lon": club.get("city_lon"),
                "city_source_url": club.get("city_source_url"),
                "city_geo_source": club.get("city_geo_source"),
                "city_match_confidence": club.get("city_match_confidence"),
                "city_review_notes": club.get("city_review_notes"),
            },
        )

    cities = []
    for city_key, city_row in sorted(grouped.items()):
        row = dict(city_row)
        row["club_count"] = len([club_id for club_id in club_ids_by_city[city_key] if club_id])
        row["club_ids"] = sorted([club_id for club_id in club_ids_by_city[city_key] if club_id])
        cities.append(normalize_row(row))
    return cities


def build_teams_from_squad_entries(squad_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in squad_entries:
        grouped[(str(row.get("team") or ""), str(row.get("team_code") or ""))].append(row)

    teams = []
    for (team, team_code), rows in sorted(grouped.items()):
        # Since the final-roster import, squad_entries also carries rows with
        # squad_status="removed" (players cut from the announced squads). The
        # team roster only counts active entries; removed rows stay available
        # through squad_entries.json for history.
        active = [row for row in rows if str(row.get("squad_status") or "active") == "active"]
        teams.append(
            normalize_row(
                {
                    "team": team,
                    "team_code": team_code,
                    "tournament": rows[0].get("tournament"),
                    "squad_size": len(active),
                    "replacement_count": sum(
                        1 for row in active if row.get("is_replacement") in (True, "TRUE", "true", "True")
                    ),
                    "players": [row.get("player_id") for row in active if row.get("player_id")],
                }
            )
        )
    return teams


def read_optional_sheet(workbook_path: str, sheet_names: list[str], sheet_name: str) -> list[dict[str, Any]]:
    if sheet_name not in sheet_names:
        return []
    return [normalize_row(row) for row in read_sheet_rows(workbook_path, sheet_name)]


def parse_confederations_md(path: Path) -> list[dict[str, Any]]:
    """Parse data/raw/confederations.md (headings + comma-separated member lists)."""
    if not path.exists():
        return []
    confederations: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            heading = line[2:].strip()
            match = re.search(r"\(([^)]+)\)\s*$", heading)
            code = match.group(1) if match else heading
            name = re.sub(r"\s*\([^)]+\)\s*$", "", heading)
            current = {"code": code, "name": name, "source_url": None, "members": []}
            confederations.append(current)
        elif line.startswith("## Source:") and current is not None:
            current["source_url"] = line.removeprefix("## Source:").strip()
        elif line and current is not None and not line.startswith("#"):
            seen = set(current["members"])
            for member in line.rstrip(".").split(","):
                member = member.strip()
                if member and member not in seen:
                    seen.add(member)
                    current["members"].append(member)
    return confederations


def workbook_clubs_are_dashboard_ready(clubs: list[dict[str, Any]]) -> bool:
    if not clubs:
        return False
    required_fields = {
        "city_lat",
        "city_lon",
        "city_source_url",
        "city_geo_source",
        "city_match_confidence",
        "city_key",
    }
    if not required_fields.issubset(clubs[0].keys()):
        return False
    return any(
        club.get("city_lat") is not None
        and club.get("city_lon") is not None
        for club in clubs
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    workbook_path = args.master_workbook
    output_dir = Path(args.output_dir)
    sheet_names = list_sheet_names(workbook_path)

    players = [normalize_row(row) for row in read_sheet_rows(workbook_path, "players")]
    squad_entries = [normalize_row(row) for row in read_sheet_rows(workbook_path, "squad_entries")]
    player_club_at_callup = [normalize_row(row) for row in read_sheet_rows(workbook_path, "player_club_at_callup")]
    sources = [normalize_row(row) for row in read_sheet_rows(workbook_path, "sources")]
    change_log = read_optional_sheet(workbook_path, sheet_names, "change_log")
    # The match-results sheet was renamed from world_cup_history to
    # match_history during the 2026-07 final-dataset import; accept either.
    world_cup_history = read_optional_sheet(workbook_path, sheet_names, "match_history") or read_optional_sheet(
        workbook_path, sheet_names, "world_cup_history"
    )
    manual_review_queue = read_optional_sheet(workbook_path, sheet_names, "manual_review_queue")
    workbook_clubs = [normalize_row(row) for row in read_sheet_rows(workbook_path, "clubs")]

    overlay_path = Path(args.club_geodata_overlay)
    if workbook_clubs_are_dashboard_ready(workbook_clubs):
        clubs = workbook_clubs
        clubs_source = f"{repo_relative(workbook_path)}:clubs"
    elif overlay_path.exists():
        clubs = [normalize_row(row) for row in read_csv_rows(overlay_path)]
        clubs_source = repo_relative(overlay_path)
    else:
        clubs = workbook_clubs
        clubs_source = f"{repo_relative(workbook_path)}:clubs"

    for club in clubs:
        if not club.get("city_key"):
            club["city_key"] = build_city_key(str(club.get("country") or ""), str(club.get("city") or ""))

    cities = build_cities_from_clubs(clubs)
    teams = build_teams_from_squad_entries(squad_entries)
    player_stats = read_optional_sheet(workbook_path, sheet_names, "player_stats")
    team_stats = read_optional_sheet(workbook_path, sheet_names, "team_stats")
    coaches = read_optional_sheet(workbook_path, sheet_names, "coaches")
    referees = read_optional_sheet(workbook_path, sheet_names, "referees")
    confederations = parse_confederations_md(REPO_ROOT / "data/raw/confederations.md")

    exports = {
        "clubs.json": clubs,
        "cities.json": cities,
        "players.json": players,
        "teams.json": teams,
        "player_stats.json": player_stats,
        "team_stats.json": team_stats,
        "coaches.json": coaches,
        "referees.json": referees,
        "confederations.json": confederations,
        "squad_entries.json": squad_entries,
        "player_club_at_callup.json": player_club_at_callup,
        "sources.json": sources,
        "change_log.json": change_log,
        "world_cup_history.json": world_cup_history,
        "matches.json": world_cup_history,
        "manual_review_queue.json": manual_review_queue,
        "meta.json": {
            "source_workbook": repo_relative(workbook_path),
            "clubs_source": clubs_source,
            "sheet_names": sheet_names,
            "counts": {
                "clubs": len(clubs),
                "cities": len(cities),
                "players": len(players),
                "teams": len(teams),
                "player_stats": len(player_stats),
                "team_stats": len(team_stats),
                "coaches": len(coaches),
                "referees": len(referees),
                "confederations": len(confederations),
                "squad_entries": len(squad_entries),
                "player_club_at_callup": len(player_club_at_callup),
                "sources": len(sources),
                "change_log": len(change_log),
                "world_cup_history": len(world_cup_history),
                "manual_review_queue": len(manual_review_queue),
            },
        },
    }

    for filename, payload in exports.items():
        write_json(output_dir / filename, payload)

    print(f"Read workbook: {workbook_path}")
    print(f"Clubs source: {clubs_source}")
    print(f"Wrote JSON exports to {output_dir}")
    for filename, payload in exports.items():
        if isinstance(payload, list):
            print(f"- {filename}: {len(payload)} rows")


if __name__ == "__main__":
    main()
