"""Cross-table consistency checks for the app-ready JSON exports.

test_export_invariants.py checks keys and references. These check that tables
built from different sources agree with each other: team records against
match results, player goals against team goals, the tournament format, and
the shape of each squad. A wrong person or a wrong number can pass a key check;
it is less likely to pass these.

Rule IDs (C3, U3, ...) are the ones the data-quality audit script uses, so a
failure here can be looked up row by row in its rule_failures.csv.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "app_exports"

# Matches per stage in the 48-team, 104-match format.
EXPECTED_STAGE_COUNTS = {
    "First Stage": 72,
    "Round of 32": 16,
    "Round of 16": 8,
    "Quarter-final": 4,
    "Semi-final": 2,
    "Play-off for third place": 1,
    "Final": 1,
}


def load(name: str) -> list | dict:
    return json.loads((EXPORT_DIR / name).read_text(encoding="utf-8"))


def blank(value: object) -> bool:
    return value is None or str(value).strip() == ""


@pytest.fixture(scope="session")
def data() -> dict:
    names = ["teams", "squad_entries", "player_stats", "team_stats", "matches", "coaches"]
    return {name: load(f"{name}.json") for name in names}


@pytest.fixture(scope="session")
def active(data: dict) -> list[dict]:
    return [e for e in data["squad_entries"] if e["squad_status"] == "active"]


def test_team_records_match_results(data: dict) -> None:
    """C3: W/D/L, goals for and against equal the totals recomputed from matches."""
    record: dict[str, Counter] = defaultdict(Counter)
    for m in data["matches"]:
        sides = ((m["home_team"], m["home_score"], m["away_score"]), (m["away_team"], m["away_score"], m["home_score"]))
        for team, gf, ga in sides:
            r = record[team]
            r["matches_played"] += 1
            r["goals_for"] += gf
            r["goals_against"] += ga
            # Level after extra time is a draw in FIFA records, whatever the shootout.
            r["wins" if gf > ga else "losses" if gf < ga else "draws"] += 1
    columns = ("matches_played", "wins", "draws", "losses", "goals_for", "goals_against")
    wrong = {
        t["team_code"]: {c: (t[c], record[t["team"]][c]) for c in columns if t[c] != record[t["team"]][c]}
        for t in data["team_stats"]
    }
    wrong = {code: diff for code, diff in wrong.items() if diff}
    assert not wrong, f"team_stats disagree with match results (stats, matches): {wrong}"


def test_player_goals_do_not_exceed_team_goals(data: dict) -> None:
    """C4: the gap is own goals scored in the team's favour, so it is never negative."""
    goals = Counter()
    for s in data["player_stats"]:
        goals[s["team_code"]] += s["goals"] or 0
    over = {
        t["team_code"]: (goals[t["team_code"]], t["goals_for"])
        for t in data["team_stats"]
        if goals[t["team_code"]] > t["goals_for"]
    }
    assert not over, f"player goals exceed team goals (players, team): {over}"


def test_indirect_reds_are_a_subset_of_reds(data: dict) -> None:
    """FIFA's red_cards already counts second-yellow sendings-off; the site must not add them twice."""
    wrong = [s["player_id"] for s in data["player_stats"] if (s.get("indirect_red_cards") or 0) > (s.get("red_cards") or 0)]
    assert not wrong, f"indirect_red_cards > red_cards for: {wrong[:5]}"


def test_one_stats_row_per_player(data: dict) -> None:
    """U5"""
    dupes = [pid for pid, n in Counter(s["player_id"] for s in data["player_stats"]).items() if n > 1]
    assert not dupes, f"players with more than one stats row: {dupes[:5]}"


def test_removed_players_have_no_tournament_stats(data: dict) -> None:
    """C6"""
    with_stats = {s["player_id"] for s in data["player_stats"]}
    removed = [e["player_id"] for e in data["squad_entries"] if e["squad_status"] == "removed" and e["player_id"] in with_stats]
    assert not removed, f"players marked removed have stats: {removed[:5]}"


def test_stage_counts_match_the_format(data: dict) -> None:
    """C7"""
    counts = Counter(m["stage"] for m in data["matches"])
    wrong = {stage: (counts.get(stage, 0), n) for stage, n in EXPECTED_STAGE_COUNTS.items() if counts.get(stage, 0) != n}
    assert not wrong, f"stage counts (found, expected): {wrong}"
    assert sum(counts.values()) == 104, f"expected 104 matches, found {sum(counts.values())}"


def test_shootouts_only_on_level_knockout_matches(data: dict) -> None:
    """C8: a shootout needs a level score in a knockout match, and every such match needs one."""
    wrong = []
    for m in data["matches"]:
        has_pens = not blank(m.get("home_pens")) or not blank(m.get("away_pens"))
        level = m["home_score"] == m["away_score"]
        knockout = m["stage"] != "First Stage"
        if has_pens != (level and knockout):
            wrong.append(m["match_id"])
    assert not wrong, f"shootout recorded or missing on: {wrong}"


def test_team_names_resolve(data: dict) -> None:
    """C9: every team name in other tables is one of the 48 canonical names."""
    names = {t["team"] for t in data["teams"]}
    stray = {
        table: sorted({r[col] for r in rows} - names)
        for table, rows, col in (
            ("coaches", data["coaches"], "team"),
            ("team_stats", data["team_stats"], "team"),
            ("matches.home_team", data["matches"], "home_team"),
            ("matches.away_team", data["matches"], "away_team"),
        )
    }
    stray = {table: bad for table, bad in stray.items() if bad}
    assert not stray, f"team names not in teams.json: {stray}"


def test_one_captain_per_squad(data: dict, active: list[dict]) -> None:
    """C1"""
    captains = Counter(e["team_code"] for e in active if e["is_captain"] is True)
    wrong = {t["team_code"]: captains.get(t["team_code"], 0) for t in data["teams"] if captains.get(t["team_code"], 0) != 1}
    assert not wrong, f"squads without exactly one captain: {wrong}"


def test_at_least_three_goalkeepers_per_squad(data: dict, active: list[dict]) -> None:
    """C2"""
    keepers = Counter(e["team_code"] for e in active if e["position_group"] == "goalkeeper")
    short = {t["team_code"]: keepers.get(t["team_code"], 0) for t in data["teams"] if keepers.get(t["team_code"], 0) < 3}
    assert not short, f"squads with fewer than 3 goalkeepers: {short}"


def test_shirt_numbers_unique_within_squad(active: list[dict]) -> None:
    """U3"""
    numbers = Counter((e["team_code"], e["shirt_number"]) for e in active if not blank(e["shirt_number"]))
    dupes = [f"{team} #{number}" for (team, number), n in numbers.items() if n > 1]
    assert not dupes, f"shirt numbers used twice in one squad: {dupes}"
