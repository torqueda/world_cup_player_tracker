"""Inputs and outputs shared by the analysis scripts."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTS = REPO_ROOT / "data/processed/app_exports"
OUTPUT_DIR = REPO_ROOT / "data/processed/analysis"

TOURNAMENT_START = "2026-06-11"
TOURNAMENT_END = "2026-07-19"

# Transfermarkt values for the final squads, written by market_values.py. A
# value counts only if it was set in the 12 months before the tournament.
MARKET_VALUES = REPO_ROOT / "data/raw/transfermarkt_wc2026_snapshot.csv"
VALUES_SET_SINCE = "2025-06-11"

# The tracker's team names where martj42, the club table and the
# confederation lists spell the country differently.
COUNTRY_NAMES = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Curacao": "Curaçao",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
}

BIG_FIVE_LEAGUES = {"Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"}


def country_name(team: str) -> str:
    return COUNTRY_NAMES.get(team, team)


def read_export(name: str):
    return json.loads((EXPORTS / f"{name}.json").read_text(encoding="utf-8"))


def write_output(name: str, payload: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_output(name: str) -> dict:
    return json.loads((OUTPUT_DIR / f"{name}.json").read_text(encoding="utf-8"))


def age_in_years(date_of_birth: str, on: str = TOURNAMENT_START) -> float:
    born, day = date.fromisoformat(date_of_birth[:10]), date.fromisoformat(on)
    return (day - born).days / 365.25


def rounded(value: float, places: int = 4) -> float:
    return round(float(value), places)


def market_values() -> dict[str, float]:
    """Each player's Transfermarkt market value in euros, where one was set in
    the 12 months before the tournament."""
    with MARKET_VALUES.open(encoding="utf-8", newline="") as handle:
        return {r["player_id"]: float(r["market_value_eur"]) for r in csv.DictReader(handle)
                if r["market_value_eur"] and r["valuation_date"] >= VALUES_SET_SINCE}


def final_squads() -> list[dict]:
    """One row per player in a final squad: the squad entry joined to the player,
    the call-up club, the team's confederation and the market value, if known."""
    players = {p["player_id"]: p for p in read_export("players")}
    values = market_values()
    clubs = {c["club_id"]: c for c in read_export("clubs")}
    callups = {c["player_id"]: c for c in read_export("player_club_at_callup")}
    confederation = {member: c["code"] for c in read_export("confederations") for member in c["members"]}
    minutes = {s["player_id"]: s["minutes_played"] for s in read_export("player_stats")}
    rows = []
    for entry in read_export("squad_entries"):
        if entry["squad_status"] != "active":
            continue
        player = players[entry["player_id"]]
        club = clubs[callups[entry["player_id"]]["club_id"]]
        rows.append({
            "player_id": entry["player_id"],
            "display_name": player["display_name"],
            "team": entry["team"],
            "confederation": confederation[country_name(entry["team"])],
            "position_group": entry["position_group"],
            "age": age_in_years(player["date_of_birth"]),
            "caps": entry["caps_pre_tournament"],
            "club_league": club["league"],
            "club_country": club["country"],
            "big_five_club": club["league"] in BIG_FIVE_LEAGUES,
            "plays_abroad": club["country"] != country_name(entry["team"]),
            "minutes": minutes.get(entry["player_id"], 0),
            "has_photo": bool(player["image_url"]),
            "market_value_eur": values.get(entry["player_id"]),
        })
    return rows
