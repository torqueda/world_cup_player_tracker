#!/usr/bin/env python3
"""
Team strength before and during the 2026 World Cup, and a pre-match forecast
for each of its 104 matches.

Data: martj42/international_results (https://github.com/martj42/international_results,
CC0), every men's international since 1872. The snapshot in data/raw was
downloaded on 2026-11-05 and trimmed to matches up to the 2026 final, so the
results here do not move when the upstream file grows.

Elo ratings follow the World Football Elo formula published at eloratings.net:
every team starts at 1500; K is 60 for World Cup matches, 50 for continental
finals, 40 for qualifiers and Nations Leagues, 30 for other tournaments and 20
for friendlies; K grows with the goal margin; the home side gets 100 points;
a shootout counts as a draw. Only matches between FIFA members count,
approximated as every team that has played a World Cup or a World Cup
qualifier, which leaves out sides such as CONIFA members.

The forecast is a symmetric ordered logit (ordered_logit.py) on the Elo gap and
the home flag, fitted to every match from 1994 to the eve of the tournament.
Each 2026 match is forecast from the ratings just before it, so the ratings
take in the earlier 2026 results, as a forecast made on the day would.

Outputs, in data/processed/analysis:
- team_strength_2026.json: each team's Elo before and after the tournament,
  its rank among the 48, and its World Cup record before 2026.
- match_forecasts_2026.json: the model, its scores against two baselines with
  95% intervals, a calibration table, and each match's forecast.

Usage:
    python scripts/analysis/team_strength.py
"""

from __future__ import annotations

import csv
import gzip
from collections import defaultdict
from datetime import date

import numpy as np

import ordered_logit as ol
from analysis_data import (
    REPO_ROOT,
    TOURNAMENT_END,
    TOURNAMENT_START,
    country_name,
    read_export,
    rounded,
    write_output,
)

RESULTS = REPO_ROOT / "data/raw/martj42_results_snapshot.csv.gz"
FORMER_NAMES = REPO_ROOT / "data/raw/martj42_former_names_snapshot.csv"
SOURCE = {
    "name": "martj42/international_results",
    "url": "https://github.com/martj42/international_results",
    "license": "CC0 1.0",
    "downloaded": "2026-11-05",
    "snapshot": "data/raw/martj42_results_snapshot.csv.gz, matches up to 2026-07-19",
}

START_RATING = 1500.0
HOME_ADVANTAGE = 100.0
TRAIN_START = "1994-01-01"
SEED = 2026

CONTINENTAL_FINALS = {
    "UEFA Euro", "Copa América", "African Cup of Nations", "AFC Asian Cup", "Gold Cup",
    "CONCACAF Championship", "Oceania Nations Cup", "Confederations Cup",
}
FEATURES = ["elo_gap_per_100", "home"]


# Elo ------------------------------------------------------------------------


def k_factor(tournament: str) -> float:
    if tournament == "FIFA World Cup":
        return 60.0
    if tournament in CONTINENTAL_FINALS:
        return 50.0
    if "qualification" in tournament or tournament in ("UEFA Nations League", "CONCACAF Nations League"):
        return 40.0
    if tournament == "Friendly":
        return 20.0
    return 30.0


def margin_multiplier(goal_margin: int) -> float:
    n = abs(goal_margin)
    return 1.0 if n <= 1 else 1.5 if n == 2 else (11 + n) / 8


def expected_result(rating_gap: float) -> float:
    """The first team's expected result (win 1, draw 0.5) for a rating gap that
    already includes any home advantage."""
    return 1.0 / (10 ** (-rating_gap / 400) + 1)


def rating_change(home_rating: float, away_rating: float, home_goals: int, away_goals: int,
                  tournament: str, neutral: bool) -> float:
    """Points the first-named team gains; the other team loses the same."""
    gap = home_rating - away_rating + (0.0 if neutral else HOME_ADVANTAGE)
    result = 1.0 if home_goals > away_goals else 0.5 if home_goals == away_goals else 0.0
    return k_factor(tournament) * margin_multiplier(home_goals - away_goals) * (result - expected_result(gap))


def load_results() -> list[dict]:
    """martj42 results under current team names, between FIFA members, in date order."""
    with FORMER_NAMES.open(encoding="utf-8", newline="") as fh:
        renames = [(r["former"], r["current"], r["start_date"], r["end_date"]) for r in csv.DictReader(fh)]

    def current(name: str, when: str) -> str:
        for former, now, start, end in renames:
            if name == former and start <= when <= end:
                return now
        return name

    with gzip.open(RESULTS, "rt", encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["home_score"] not in ("", "NA")]
    for r in rows:
        r["home_team"] = current(r["home_team"], r["date"])
        r["away_team"] = current(r["away_team"], r["date"])
        r["home_score"], r["away_score"] = int(r["home_score"]), int(r["away_score"])
        r["neutral"] = r["neutral"] == "TRUE"
    members = {
        team for r in rows if r["tournament"] in ("FIFA World Cup", "FIFA World Cup qualification")
        for team in (r["home_team"], r["away_team"])
    }
    rows = [r for r in rows if r["home_team"] in members and r["away_team"] in members]
    return sorted(rows, key=lambda r: r["date"])  # stable: keeps the file's order within a day


def rate(rows: list[dict]) -> tuple[list[dict], dict[str, dict[str, float]]]:
    """Walk the matches in order. Adds each match's pre-match ratings to its row
    and returns the rows with every team's rating on the eve of the tournament
    and at the end of the snapshot."""
    ratings: dict[str, float] = defaultdict(lambda: START_RATING)
    before: dict[str, float] | None = None
    for r in rows:
        if before is None and r["date"] >= TOURNAMENT_START:
            before = dict(ratings)
        home, away = r["home_team"], r["away_team"]
        r["home_elo"], r["away_elo"] = ratings[home], ratings[away]
        change = rating_change(ratings[home], ratings[away], r["home_score"], r["away_score"],
                               r["tournament"], r["neutral"])
        ratings[home] += change
        ratings[away] -= change
    return rows, {"before": before or dict(ratings), "after": dict(ratings)}


# Forecasts ------------------------------------------------------------------


def features(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    X = np.array([[(r["home_elo"] - r["away_elo"]) / 100, 0.0 if r["neutral"] else 1.0] for r in rows])
    y = np.array([ol.outcome(r["home_score"], r["away_score"]) for r in rows])
    return X, y


def world_cup_2026(rows: list[dict]) -> list[dict]:
    """The tracker's 104 matches, each with its martj42 row seen from the
    tracker's home team."""
    tracked = read_export("matches")
    by_pair: dict[frozenset, list[dict]] = defaultdict(list)
    for r in rows:
        if r["tournament"] == "FIFA World Cup" and TOURNAMENT_START <= r["date"] <= TOURNAMENT_END:
            by_pair[frozenset((r["home_team"], r["away_team"]))].append(r)
    matched = []
    for match in tracked:
        home, away = country_name(match["home_team"]), country_name(match["away_team"])
        day = date.fromisoformat(match["match_date"][:10])
        candidates = [r for r in by_pair[frozenset((home, away))]
                      if abs((date.fromisoformat(r["date"]) - day).days) <= 1]
        if len(candidates) != 1:
            raise ValueError(f"{match['match_id']}: {len(candidates)} martj42 rows for {home} v {away}")
        r = candidates[0]
        flipped = r["home_team"] != home
        row = {
            "match": match,
            "home_elo": r["away_elo"] if flipped else r["home_elo"],
            "away_elo": r["home_elo"] if flipped else r["away_elo"],
            # +1 when the tracker's home team is at home, -1 when its opponent is.
            "home": 0.0 if r["neutral"] else (-1.0 if flipped else 1.0),
            "home_score": r["away_score"] if flipped else r["home_score"],
            "away_score": r["home_score"] if flipped else r["away_score"],
        }
        if (row["home_score"], row["away_score"]) != (match["home_score"], match["away_score"]):
            raise ValueError(f"{match['match_id']}: martj42 has {row['home_score']}-{row['away_score']}, "
                             f"the tracker {match['home_score']}-{match['away_score']}")
        matched.append(row)
    return matched


def calibration(P: np.ndarray, y: np.ndarray) -> list[dict]:
    """Every forecast probability (three per match) against how often that
    result happened, in bands of 0.2."""
    forecast = P.ravel()
    happened = np.eye(3)[y].ravel()
    bands = []
    for low in (0.0, 0.2, 0.4, 0.6, 0.8):
        high = low + 0.2
        inside = (forecast >= low) & ((forecast < high) if high < 1 else (forecast <= 1))
        bands.append({
            "band": [rounded(low, 1), rounded(high, 1)],
            "forecasts": int(inside.sum()),
            "mean_forecast": rounded(forecast[inside].mean()) if inside.any() else None,
            "share_that_happened": rounded(happened[inside].mean()) if inside.any() else None,
        })
    return bands


def score_table(forecasts: dict[str, np.ndarray], y: np.ndarray, reference: str) -> list[dict]:
    rows = []
    for name, P in forecasts.items():
        row = {"forecast": name}
        for score, fn in ol.SCORES.items():
            values = fn(P, y)
            row[score] = rounded(values.mean())
            row[f"{score}_ci95"] = [rounded(v) for v in ol.bootstrap_ci(values, SEED)]
            if name != reference:
                gap = values - fn(forecasts[reference], y)
                row[f"{score}_minus_{reference}"] = rounded(gap.mean())
                row[f"{score}_minus_{reference}_ci95"] = [rounded(v) for v in ol.bootstrap_ci(gap, SEED)]
        rows.append(row)
    return rows


def build() -> tuple[dict, dict]:
    rows, ratings = rate(load_results())
    train = [r for r in rows if TRAIN_START <= r["date"] < TOURNAMENT_START]
    X_train, y_train = features(train)
    model = ol.fit(X_train, y_train, FEATURES)

    matches = world_cup_2026(rows)
    X = np.array([[(m["home_elo"] - m["away_elo"]) / 100, m["home"]] for m in matches])
    y = np.array([ol.outcome(m["home_score"], m["away_score"]) for m in matches])
    P = model.predict(X)  # [P(away win), P(draw), P(home win)]: the home team's loss, draw, win
    draw_rate = float((y_train == ol.DRAW).mean())
    forecasts = {
        "elo_model": P,
        "draw_rate_only": np.tile([(1 - draw_rate) / 2, draw_rate, (1 - draw_rate) / 2], (len(y), 1)),
        "one_third_each": np.full((len(y), 3), 1 / 3),
    }

    per_match = []
    for m, p, outcome in zip(matches, P, y):
        match = m["match"]
        per_match.append({
            "match_id": match["match_id"],
            "match_date": match["match_date"][:10],
            "stage": match["stage"],
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "home_elo_before": rounded(m["home_elo"], 1),
            "away_elo_before": rounded(m["away_elo"], 1),
            "at_home": match["home_team"] if m["home"] > 0 else match["away_team"] if m["home"] < 0 else None,
            "p_home_win": rounded(p[ol.WIN]),
            "p_draw": rounded(p[ol.DRAW]),
            "p_away_win": rounded(p[ol.LOSS]),
            "home_score": m["home_score"],
            "away_score": m["away_score"],
            "result": ("away_win", "draw", "home_win")[outcome],
            "p_result": rounded(p[outcome]),
            "ranked_probability_score": rounded(ol.ranked_probability_score(p[None, :], np.array([outcome]))[0]),
        })

    coefficients = model.coefficients()
    forecasts_payload = {
        "about": {
            "what": "Pre-match win, draw and loss probabilities for the 104 matches of the 2026 World Cup, "
                    "from a model of Elo ratings. A model's forecast, not a betting line or an official rating.",
            "source": SOURCE,
            "model": "Symmetric ordered logit on the Elo gap (per 100 points) and the home flag "
                     "(scripts/analysis/ordered_logit.py)",
            "trained_on": {
                "from": TRAIN_START,
                "to_before": TOURNAMENT_START,
                "matches": int(len(y_train)),
                "draw_share": rounded(draw_rate),
            },
            "coefficients": [
                {**c, "coefficient": rounded(c["coefficient"]), "std_error": rounded(c["std_error"]),
                 "odds_ratio": rounded(c["odds_ratio"]), "odds_ratio_ci95": [rounded(v) for v in c["odds_ratio_ci95"]]}
                for c in coefficients
            ],
            "cut": rounded(model.cut),
            "draw_chance_between_equal_teams": rounded(model.predict(np.zeros((1, 2)))[0, ol.DRAW]),
            "results": "After extra time; a shootout counts as a draw.",
            "ratings": "Each match uses both teams' Elo ratings just before it, so the ratings take in the earlier "
                       "2026 results.",
            "scores": "Mean per match, lower is better except accuracy. Intervals are 95% bootstrap intervals over "
                      "the 104 matches. *_minus_elo_model is the paired gap to the Elo model: above zero means "
                      "worse than the model.",
        },
        "scores": score_table(forecasts, y, "elo_model"),
        "calibration": calibration(P, y),
        "matches": per_match,
    }

    record: dict[str, dict] = defaultdict(lambda: {"years": set(), "matches": 0, "wins": 0, "draws": 0, "losses": 0,
                                                   "goals_for": 0, "goals_against": 0})
    for r in rows:
        if r["tournament"] != "FIFA World Cup" or r["date"] >= TOURNAMENT_START:
            continue
        for team, scored, conceded in ((r["home_team"], r["home_score"], r["away_score"]),
                                       (r["away_team"], r["away_score"], r["home_score"])):
            t = record[team]
            t["years"].add(r["date"][:4])
            t["matches"] += 1
            t[("losses", "draws", "wins")[ol.outcome(scored, conceded)]] += 1
            t["goals_for"] += scored
            t["goals_against"] += conceded

    teams = read_export("teams")
    before, after = ratings["before"], ratings["after"]
    rank_before = {t["team"]: i for i, t in enumerate(sorted(teams, key=lambda t: -before[country_name(t["team"])]), 1)}
    rank_after = {t["team"]: i for i, t in enumerate(sorted(teams, key=lambda t: -after[country_name(t["team"])]), 1)}
    team_rows = []
    for t in sorted(teams, key=lambda t: rank_before[t["team"]]):
        name = country_name(t["team"])
        history = record.get(name)
        years = sorted(history["years"]) if history else []
        team_rows.append({
            "team": t["team"],
            "team_code": t["team_code"],
            "elo_before": rounded(before[name], 1),
            "elo_after": rounded(after[name], 1),
            "elo_change": rounded(after[name] - before[name], 1),
            "rank_before": rank_before[t["team"]],
            "rank_after": rank_after[t["team"]],
            "world_cups_before_2026": len(years),
            "first_world_cup": int(years[0]) if years else None,
            **{key: (history[key] if history else 0)
               for key in ("matches", "wins", "draws", "losses", "goals_for", "goals_against")},
        })
    strength_payload = {
        "about": {
            "what": "Each team's World Football Elo rating on the eve of the 2026 World Cup and after the final, "
                    "rebuilt from every international since 1872, and its World Cup record before 2026.",
            "source": SOURCE,
            "elo": "eloratings.net formula: start 1500; K 60 World Cup, 50 continental finals, 40 qualifiers and "
                   "Nations Leagues, 30 other tournaments, 20 friendlies, scaled up by the goal margin; 100 points "
                   "for the home side; a shootout counts as a draw. Matches between FIFA members only.",
            "ranks": "Among the 48 teams at the tournament.",
            "world_cup_record": "Finals matches before 2026 under martj42's team names, which carry a country's "
                                "record across a change of name (West Germany is Germany, the Soviet Union is "
                                "Russia, Serbia and Montenegro is Serbia). Results after extra time; a shootout "
                                "counts as a draw.",
            "matches_rated": len(rows),
        },
        "teams": team_rows,
    }
    return strength_payload, forecasts_payload


def main() -> None:
    strength, forecasts = build()
    for name, payload in (("team_strength_2026", strength), ("match_forecasts_2026", forecasts)):
        print(f"Wrote {write_output(name, payload).relative_to(REPO_ROOT)}")
    elo = next(s for s in forecasts["scores"] if s["forecast"] == "elo_model")
    print(f"{strength['about']['matches_rated']} matches rated; Elo model RPS {elo['ranked_probability_score']} "
          f"(95% interval {elo['ranked_probability_score_ci95']}) on {len(forecasts['matches'])} matches")


if __name__ == "__main__":
    main()
