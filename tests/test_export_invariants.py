"""Integrity checks for the app-ready JSON exports.

These assert the invariants the dashboard relies on: unique keys, referential
integrity across the relational tables, the 48x26 active-roster shape, and
meta.json counts that match the files they describe. They run against whatever
is currently in data/processed/app_exports/, so running the export pipeline and
then pytest catches any regression before it can reach the live site.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "app_exports"


def load(name: str) -> list | dict:
    return json.loads((EXPORT_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def data() -> dict:
    names = [
        "players",
        "clubs",
        "cities",
        "teams",
        "squad_entries",
        "player_club_at_callup",
        "club_aliases",
        "player_stats",
        "team_stats",
        "coaches",
        "referees",
        "confederations",
        "matches",
        "meta",
    ]
    return {name: load(f"{name}.json") for name in names}


def test_export_dir_exists() -> None:
    assert EXPORT_DIR.is_dir(), f"missing export dir {EXPORT_DIR}; run refresh_all_exports.py first"


def test_player_ids_unique(data: dict) -> None:
    ids = [p["player_id"] for p in data["players"]]
    assert len(ids) == len(set(ids)), "duplicate player_id values in players.json"


def test_club_ids_unique(data: dict) -> None:
    ids = [c["club_id"] for c in data["clubs"]]
    assert len(ids) == len(set(ids)), "duplicate club_id values in clubs.json"


def test_squad_entries_reference_real_players(data: dict) -> None:
    player_ids = {p["player_id"] for p in data["players"]}
    missing = {e["player_id"] for e in data["squad_entries"] if e["player_id"] not in player_ids}
    assert not missing, f"squad_entries reference unknown player_ids: {sorted(missing)[:5]}"


def test_player_club_links_reference_real_rows(data: dict) -> None:
    player_ids = {p["player_id"] for p in data["players"]}
    club_ids = {c["club_id"] for c in data["clubs"]}
    bad_players = {link["player_id"] for link in data["player_club_at_callup"] if link["player_id"] not in player_ids}
    bad_clubs = {link["club_id"] for link in data["player_club_at_callup"] if link["club_id"] not in club_ids}
    assert not bad_players, f"player_club_at_callup references unknown player_ids: {sorted(bad_players)[:5]}"
    assert not bad_clubs, f"player_club_at_callup references unknown club_ids: {sorted(bad_clubs)[:5]}"


def test_cities_reference_real_clubs(data: dict) -> None:
    club_ids = {c["club_id"] for c in data["clubs"]}
    for city in data["cities"]:
        unknown = [cid for cid in city["club_ids"] if cid not in club_ids]
        assert not unknown, f"city {city['city_key']} references unknown club_ids: {unknown[:5]}"


def test_club_aliases_resolve(data: dict) -> None:
    club_ids = {c["club_id"] for c in data["clubs"]}
    unresolved = [a["alias"] for a in data["club_aliases"] if a["canonical_club_id"] not in club_ids]
    assert not unresolved, f"club_aliases point to unknown clubs: {unresolved[:5]}"


def test_48_teams(data: dict) -> None:
    assert len(data["teams"]) == 48, f"expected 48 teams, found {len(data['teams'])}"


def test_each_active_squad_has_26_players(data: dict) -> None:
    counts: dict[str, int] = {}
    for entry in data["squad_entries"]:
        if entry["squad_status"] == "active":
            counts[entry["team_code"]] = counts.get(entry["team_code"], 0) + 1
    assert len(counts) == 48, f"expected 48 teams with an active squad, found {len(counts)}"
    wrong = {code: n for code, n in counts.items() if n != 26}
    assert not wrong, f"teams whose active squad is not 26 players: {wrong}"


def test_stats_reference_real_teams(data: dict) -> None:
    team_codes = {t["team_code"] for t in data["teams"]}
    bad_team_stats = {s["team_code"] for s in data["team_stats"] if s["team_code"] not in team_codes}
    bad_player_stats = {s["team_code"] for s in data["player_stats"] if s["team_code"] not in team_codes}
    assert not bad_team_stats, f"team_stats reference unknown team_codes: {sorted(bad_team_stats)}"
    assert not bad_player_stats, f"player_stats reference unknown team_codes: {sorted(bad_player_stats)}"


def test_meta_counts_match_files(data: dict) -> None:
    counts = data["meta"]["counts"]
    for key, expected in counts.items():
        path = EXPORT_DIR / f"{key}.json"
        if not path.exists():
            # A retired sheet (e.g. manual_review_queue) may report 0 with no file.
            assert expected == 0, f"meta counts {key}={expected} but {key}.json is missing"
            continue
        actual = len(json.loads(path.read_text(encoding="utf-8")))
        assert actual == expected, f"meta count for {key} is {expected} but {key}.json has {actual} rows"
