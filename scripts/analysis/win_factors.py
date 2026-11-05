#!/usr/bin/env python3
"""
What went with winning at the 2026 World Cup: squad age, caps, the share of
the squad at big-five league clubs, squad market value, Elo rating and playing
at home.

Each of the 104 matches gets the difference between the two teams on each
factor (first team minus second), and a symmetric ordered logit
(ordered_logit.py) relates the differences to win, draw or loss:

- elo_only: the Elo gap before the match and the home flag.
- <factor>_alone: one squad factor and the home flag, the plain association.
- elo_plus_<factor>: the factor added to elo_only, which shows whether it adds
  anything once team strength is known. A likelihood-ratio test and
  leave-one-out forecasts (each match forecast from a model fitted to the
  other 103) compare it with elo_only.
- all_factors: everything together.
- elo_plus_big_five_and_confederation: a check on the big-five result, with a
  flag for teams from UEFA or CONMEBOL, in case the big-five share only
  stands for where a team plays its qualifiers.

The factor list was fixed before the models were fitted. Squad market value
was on it from the start and was added when its data arrived
(market_values.py). It is the combined value of each team's 11 most valuable
players, which approximates a starting eleven and depends least on the
players Transfermarkt has no recent value for, mostly squad players at clubs
outside the leagues it covers. Iran has recent values for only 9 players, so
its figure is low.

Team-level Spearman correlations, with bootstrap 95% intervals over the 48
teams, relate the factors to points per match and to the Elo points each team
gained over the tournament.

One tournament is 104 matches, so only strong effects can show, and the
factors overlap: teams with more big-five players also have higher ratings.
These are associations, not causes.

Inputs: the app exports (final squads, players, clubs, team stats) and
data/processed/analysis/{team_strength,match_forecasts}_2026.json from
team_strength.py.

Output: data/processed/analysis/win_factors_2026.json

Usage:
    python scripts/analysis/win_factors.py
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.stats import rankdata, spearmanr

import ordered_logit as ol
from analysis_data import REPO_ROOT, final_squads, read_export, read_output, rounded, write_output

SEED = 2026
# Squad factors: name -> (team-level column, scale of the match-level
# difference, unit the odds ratio is reported per).
SQUAD_FACTORS = {
    "age_gap": ("mean_age", 1.0, "1 year of average age"),
    "caps_gap_per_10": ("mean_caps", 10.0, "10 caps of average experience"),
    "big_five_gap_per_10pts": ("big_five_share", 0.1, "10 percentage points of the squad at big-five clubs"),
    "value_gap_per_doubling": ("log2_top11_value", 1.0, "a doubling of the market value of the 11 most valuable players"),
}
BASE = ["elo_gap_per_100", "home"]
CONFEDERATION = "uefa_or_conmebol_gap"
UNITS = {
    "elo_gap_per_100": "100 Elo points",
    "home": "playing at home",
    CONFEDERATION: "a UEFA or CONMEBOL team against one from elsewhere",
} | {k: v[2] for k, v in SQUAD_FACTORS.items()}


def team_table() -> list[dict]:
    squads: dict[str, list[dict]] = defaultdict(list)
    for row in final_squads():
        squads[row["team"]].append(row)
    strength = {t["team"]: t for t in read_output("team_strength_2026")["teams"]}
    stats = {t["team"]: t for t in read_export("team_stats")}
    hosts = {m["at_home"] for m in read_output("match_forecasts_2026")["matches"] if m["at_home"]}
    rows = []
    for team in sorted(squads):
        squad, s = squads[team], stats[team]
        values = sorted((p["market_value_eur"] for p in squad if p["market_value_eur"] is not None), reverse=True)
        rows.append({
            "team": team,
            "confederation": squad[0]["confederation"],
            "squad_size": len(squad),
            "mean_age": rounded(np.mean([p["age"] for p in squad]), 3),
            "mean_caps": rounded(np.mean([p["caps"] for p in squad]), 2),
            "big_five_share": rounded(np.mean([p["big_five_club"] for p in squad]), 4),
            "players_valued": len(values),
            "squad_value_eur": int(sum(values)),
            "top11_value_eur": int(sum(values[:11])),
            "log2_top11_value": rounded(np.log2(sum(values[:11])), 4),
            "elo_before": strength[team]["elo_before"],
            "host": team in hosts,
            "matches": s["matches_played"],
            "points_per_match": rounded((3 * s["wins"] + s["draws"]) / s["matches_played"], 4),
            "elo_change": strength[team]["elo_change"],
        })
    return rows


def match_table(teams: dict[str, dict]) -> tuple[dict[str, np.ndarray], np.ndarray]:
    matches = read_output("match_forecasts_2026")["matches"]
    columns: dict[str, list[float]] = defaultdict(list)
    for m in matches:
        home, away = teams[m["home_team"]], teams[m["away_team"]]
        columns["elo_gap_per_100"].append((m["home_elo_before"] - m["away_elo_before"]) / 100)
        at_home = m["at_home"]
        columns["home"].append(1.0 if at_home == m["home_team"] else -1.0 if at_home == m["away_team"] else 0.0)
        for name, (column, scale, _) in SQUAD_FACTORS.items():
            columns[name].append((home[column] - away[column]) / scale)
        strong = [float(t["confederation"] in ("UEFA", "CONMEBOL")) for t in (home, away)]
        columns[CONFEDERATION].append(strong[0] - strong[1])
    y = np.array([{"away_win": ol.LOSS, "draw": ol.DRAW, "home_win": ol.WIN}[m["result"]] for m in matches])
    return {k: np.array(v) for k, v in columns.items()}, y


def leave_one_out_rps(X: np.ndarray, y: np.ndarray, names: list[str], full: ol.Fit) -> np.ndarray:
    """Each match's RPS when it is forecast from a model fitted to the others."""
    start = np.concatenate([full.beta, [np.log(full.cut)]])
    scores = np.empty(len(y))
    for i in range(len(y)):
        keep = np.arange(len(y)) != i
        fit = ol.fit(X[keep], y[keep], names, start=start)
        scores[i] = ol.ranked_probability_score(fit.predict(X[i:i + 1]), y[i:i + 1])[0]
    return scores


def describe(name: str, features: list[str], columns: dict[str, np.ndarray], y: np.ndarray,
             elo_only: tuple[ol.Fit, np.ndarray] | None) -> tuple[ol.Fit, np.ndarray, dict]:
    X = np.column_stack([columns[f] for f in features])
    fit = ol.fit(X, y, features)
    loo = leave_one_out_rps(X, y, features, fit)
    coefficients = []
    for c in fit.coefficients():
        sd = float(np.std(columns[c["feature"]]))
        coefficients.append({
            "feature": c["feature"],
            "per": UNITS[c["feature"]],
            "odds_ratio": rounded(c["odds_ratio"]),
            "odds_ratio_ci95": [rounded(v) for v in c["odds_ratio_ci95"]],
            "odds_ratio_per_sd": rounded(np.exp(c["coefficient"] * sd)) if c["feature"] != "home" else None,
            "p_value": rounded(c["p_value"]),
        })
    row = {
        "model": name,
        "features": features,
        "coefficients": coefficients,
        "loglike": rounded(fit.loglike),
        "aic": rounded(2 * (len(features) + 1) - 2 * fit.loglike),
        "leave_one_out_rps": rounded(loo.mean()),
    }
    if elo_only is not None and set(BASE) < set(features):
        base_fit, base_loo = elo_only
        row["lr_test_p_vs_elo_only"] = rounded(ol.likelihood_ratio_p(base_fit, fit))
        row["leave_one_out_rps_minus_elo_only"] = rounded((loo - base_loo).mean())
        row["leave_one_out_rps_minus_elo_only_ci95"] = [rounded(v) for v in ol.bootstrap_ci(loo - base_loo, SEED)]
    return fit, loo, row


def spearman_ci(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, resamples: int = 10_000) -> list[float]:
    """Percentile 95% interval of Spearman's rho, resampling teams."""
    idx = rng.integers(0, len(x), size=(resamples, len(x)))
    rx, ry = rankdata(x[idx], axis=1), rankdata(y[idx], axis=1)
    rx -= rx.mean(axis=1, keepdims=True)
    ry -= ry.mean(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = (rx * ry).sum(axis=1) / np.sqrt((rx ** 2).sum(axis=1) * (ry ** 2).sum(axis=1))
    return [rounded(np.nanpercentile(rho, 2.5)), rounded(np.nanpercentile(rho, 97.5))]


def build() -> dict:
    teams = team_table()
    columns, y = match_table({t["team"]: t for t in teams})

    models = []
    elo_fit, elo_loo, row = describe("elo_only", BASE, columns, y, None)
    models.append(row)
    base = (elo_fit, elo_loo)
    for factor in SQUAD_FACTORS:
        models.append(describe(f"{factor}_alone", [factor, "home"], columns, y, None)[2])
        models.append(describe(f"elo_plus_{factor}", BASE + [factor], columns, y, base)[2])
    models.append(describe("all_factors", BASE + list(SQUAD_FACTORS), columns, y, base)[2])
    models.append(describe("elo_plus_big_five_and_confederation",
                           BASE + ["big_five_gap_per_10pts", CONFEDERATION], columns, y, base)[2])

    rng = np.random.default_rng(SEED)
    team_factors = ["mean_age", "mean_caps", "big_five_share", "elo_before", "top11_value_eur"]
    team_level = []
    for factor in team_factors:
        x = np.array([t[factor] for t in teams], dtype=float)
        for outcome in ("points_per_match", "elo_change"):
            if factor == "elo_before" and outcome == "elo_change":
                continue  # the change is measured against the same rating
            z = np.array([t[outcome] for t in teams], dtype=float)
            team_level.append({
                "factor": factor,
                "outcome": outcome,
                "spearman": rounded(spearmanr(x, z).statistic),
                "spearman_ci95": spearman_ci(x, z, rng),
            })
    overlap = []
    for i, a in enumerate(team_factors):
        for b in team_factors[i + 1:]:
            rho = spearmanr([t[a] for t in teams], [t[b] for t in teams]).statistic
            overlap.append({"factors": [a, b], "spearman": rounded(rho)})

    return {
        "about": {
            "what": "How squad age, caps, big-five league players, squad market value, Elo rating and playing at "
                    "home went with results at the 2026 World Cup. Associations on one tournament, not causes.",
            "matches": int(len(y)),
            "teams": len(teams),
            "squads": "Final squads (26 players). Age on 2026-06-11; caps before the tournament; big-five clubs are "
                      "those in the Premier League, La Liga, Bundesliga, Serie A or Ligue 1 at call-up.",
            "results": "Win, draw or loss after extra time; a shootout counts as a draw.",
            "model": "Symmetric ordered logit on the differences between the two teams "
                     "(scripts/analysis/ordered_logit.py). Odds ratios are per the unit given, for the first team "
                     "doing better (a win rather than a draw, or a draw rather than a loss); odds_ratio_per_sd is per "
                     "standard deviation of the match-level difference. leave_one_out_rps forecasts each match from "
                     "a model fitted to the other 103 (lower is better); *_minus_elo_only below zero means better "
                     "forecasts than elo_only, with a 95% bootstrap interval over matches.",
            "factors_fixed_in_advance": "The factor list was fixed before the models were fitted. Squad market "
                                        "value was on it from the start and was added when its data arrived.",
            "market_value": "Transfermarkt values set in the 12 months before the tournament "
                            "(data/raw/transfermarkt_wc2026_snapshot.csv, from market_values.py). The factor is the "
                            "combined value of each team's 11 most valuable players, on a log2 scale, so its odds "
                            "ratio is per doubling. players_valued counts the players with a recent value; Iran has "
                            "9, so its figure is low.",
            "team_level": "Spearman correlations over the 48 teams with 95% bootstrap intervals.",
            "limits": "One World Cup is 104 matches, so only strong effects can show, and the factors overlap "
                      "(see factor_overlap). In all_factors, age and caps move together, so their separate "
                      "coefficients are not reliable.",
        },
        "teams": teams,
        "match_models": models,
        "team_level": team_level,
        "factor_overlap": overlap,
    }


def main() -> None:
    payload = build()
    print(f"Wrote {write_output('win_factors_2026', payload).relative_to(REPO_ROOT)}")
    for m in payload["match_models"]:
        coefficients = ", ".join(f"{c['feature']} OR {c['odds_ratio']} {c['odds_ratio_ci95']}"
                                 for c in m["coefficients"])
        gain = m.get("leave_one_out_rps_minus_elo_only", "-")
        gain_ci = m.get("leave_one_out_rps_minus_elo_only_ci95", "")
        print(f"{m['model']:36} LOO RPS {m['leave_one_out_rps']} (vs elo_only {gain} {gain_ci}) "
              f"LR p {m.get('lr_test_p_vs_elo_only', '-')}  {coefficients}")


if __name__ == "__main__":
    main()
