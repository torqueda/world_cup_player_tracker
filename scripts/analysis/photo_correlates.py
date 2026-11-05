#!/usr/bin/env python3
"""
Who has a photo on Wikimedia Commons? A light-hearted look at which traits go
with a 2026 World Cup player having one.

The outcome is whether the player's Wikidata entry links a Commons photo, as
collected for the site in July 2026 (scripts/image_collection). A logistic
regression over the 1,248 players in the final squads relates it to position,
age, caps before the tournament, playing at a big-five league club, playing
abroad, the team's confederation and minutes played at the tournament. A
second model adds the player's Transfermarkt market value, on the players with
a value set in the 12 months before the tournament (market_values.py).

Associations only: nothing here says what makes a photographer turn up, and
photos uploaded after the collection are not counted.

Outputs data/processed/analysis/photo_correlates_2026.json with:
- each model's odds ratios and average marginal effects, with 95% intervals,
- its discrimination (AUC) in sample and in 10-fold cross-validation,
- photo shares by group, and a few curiosities.

Usage:
    python scripts/analysis/photo_correlates.py
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

import numpy as np
import statsmodels.api as sm
from scipy.stats import rankdata

from analysis_data import REPO_ROOT, final_squads, rounded, write_output

POSITIONS = ["goalkeeper", "defender", "forward"]  # midfielder is the reference
CONFEDERATIONS = ["AFC", "CAF", "CONCACAF", "CONMEBOL", "OFC"]  # UEFA is the reference
FOLDS = 10
CAPS_BANDS = [(0, 0), (1, 9), (10, 29), (30, 59), (60, 99), (100, None)]
MINUTES_BANDS = [(0, 0), (1, 269), (270, None)]
VALUE_BANDS_M = [(0, 1), (1, 5), (5, 20), (20, 50), (50, None)]  # millions of euros

LABELS = {
    "goalkeeper": "Goalkeeper (against a midfielder)",
    "defender": "Defender (against a midfielder)",
    "forward": "Forward (against a midfielder)",
    "age_per_5_years": "5 years older",
    "caps_doublings": "Twice the caps",
    "big_five_club": "Plays in a big-five league",
    "plays_abroad": "Plays abroad",
    "AFC": "AFC team (against UEFA)",
    "CAF": "CAF team (against UEFA)",
    "CONCACAF": "CONCACAF team (against UEFA)",
    "CONMEBOL": "CONMEBOL team (against UEFA)",
    "OFC": "New Zealand, the one OFC team (against UEFA)",
    "matches_played_90": "90 more minutes at the tournament",
    "value_doublings": "Twice the market value",
}


def design(players: list[dict], with_value: bool = False) -> tuple[np.ndarray, np.ndarray, list[str]]:
    names = (POSITIONS + ["age_per_5_years", "caps_doublings", "big_five_club", "plays_abroad"]
             + CONFEDERATIONS + ["matches_played_90"] + (["value_doublings"] if with_value else []))
    rows = []
    for p in players:
        rows.append(
            [float(p["position_group"] == pos) for pos in POSITIONS]
            + [p["age"] / 5, np.log2(1 + p["caps"]), float(p["big_five_club"]), float(p["plays_abroad"])]
            + [float(p["confederation"] == c) for c in CONFEDERATIONS]
            + [p["minutes"] / 90]
            + ([np.log2(p["market_value_eur"])] if with_value else [])
        )
    X = sm.add_constant(np.array(rows), has_constant="add")
    y = np.array([float(p["has_photo"]) for p in players])
    return X, y, ["const"] + names


def auc(scores: np.ndarray, y: np.ndarray) -> float:
    """Area under the ROC curve: the chance that a player with a photo scores
    higher than one without (ties count half)."""
    ranks = rankdata(scores)
    positives = y == 1
    n_pos, n_neg = positives.sum(), (~positives).sum()
    return float((ranks[positives].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def fold_of(player_id: str) -> int:
    return int(hashlib.sha1(player_id.encode("utf-8")).hexdigest(), 16) % FOLDS


def cross_validated_auc(players: list[dict], X: np.ndarray, y: np.ndarray) -> float:
    folds = np.array([fold_of(p["player_id"]) for p in players])
    predicted = np.empty(len(y))
    for k in range(FOLDS):
        test = folds == k
        result = sm.Logit(y[~test], X[~test]).fit(disp=False)
        predicted[test] = result.predict(X[test])
    return auc(predicted, y)


def band_label(low: int, high: int | None, unit: str) -> str:
    if high is None:
        return f"{low}+ {unit}"
    return f"{low} {unit}" if low == high else f"{low} to {high} {unit}"


def shares(players: list[dict], key, groups: list[tuple[str, object]]) -> list[dict]:
    rows = []
    for label, test in groups:
        members = [p for p in players if test(key(p))]
        with_photo = sum(p["has_photo"] for p in members)
        rows.append({"group": label, "players": len(members), "with_photo": with_photo,
                     "share": rounded(with_photo / len(members)) if members else None})
    return rows


def in_band(low: int, high: int | None):
    return lambda value: value >= low and (high is None or value <= high)


def logit(players: list[dict], with_value: bool = False) -> tuple[list[dict], dict, np.ndarray]:
    """Fit the photo model; return its coefficients, its fit statistics and the outcome."""
    X, y, names = design(players, with_value)
    result = sm.Logit(y, X).fit(disp=False)
    if not result.mle_retvals["converged"]:
        raise RuntimeError("photo model did not converge")
    margins = result.get_margeff(at="overall", method="dydx", dummy=True)
    ame, ame_ci = margins.margeff, margins.conf_int()
    params, ci, pvalues = result.params, result.conf_int(), result.pvalues

    coefficients = []
    for i, name in enumerate(names[1:], start=1):
        coefficients.append({
            "feature": name,
            "label": LABELS[name],
            "odds_ratio": rounded(np.exp(params[i])),
            "odds_ratio_ci95": [rounded(np.exp(ci[i, 0])), rounded(np.exp(ci[i, 1]))],
            "p_value": rounded(pvalues[i]),
            "average_marginal_effect_points": rounded(100 * ame[i - 1], 2),
            "average_marginal_effect_points_ci95": [rounded(100 * v, 2) for v in ame_ci[i - 1]],
        })
    fit = {
        "players": len(players),
        "auc_in_sample": rounded(auc(result.predict(X), y)),
        "auc_cross_validated": rounded(cross_validated_auc(players, X, y)),
        "folds": FOLDS,
        "pseudo_r2_mcfadden": rounded(result.prsquared),
    }
    return coefficients, fit, y


def value_band(value: float | None) -> str:
    if value is None:
        return "no recent value"
    for low, high in VALUE_BANDS_M:
        if high is None or value < high * 1e6:
            return f"€{low}m+" if high is None else f"€{low}m to €{high}m"
    raise AssertionError(value)


def build() -> dict:
    players = sorted(final_squads(), key=lambda p: p["player_id"])
    coefficients, fit, y = logit(players)
    valued = [p for p in players if p["market_value_eur"] is not None]
    value_coefficients, value_fit, _ = logit(valued, with_value=True)

    by_team: dict[str, list[dict]] = defaultdict(list)
    for p in players:
        by_team[p["team"]].append(p)
    team_shares = sorted(((sum(p["has_photo"] for p in squad) / len(squad), team) for team, squad in by_team.items()))
    no_photo = sorted((p for p in players if not p["has_photo"]), key=lambda p: (-p["caps"], p["display_name"]))
    centurions = [p for p in players if p["caps"] >= 100]
    priciest_without_photo = sorted((p for p in valued if not p["has_photo"]), key=lambda p: -p["market_value_eur"])

    return {
        "about": {
            "what": "Which traits go with a 2026 World Cup player having a Wikimedia Commons photo. Light-hearted, "
                    "and associations only.",
            "outcome": "The player's Wikidata entry links a Commons photo, as collected for the site in July 2026.",
            "players": len(players),
            "with_photo": int(y.sum()),
            "model": "Logistic regression (statsmodels Logit). Odds ratios compare the named group with the "
                     "reference (a midfielder; a UEFA team) or give the change per unit, holding the other traits "
                     "fixed. Average marginal effects are in percentage points of the chance of having a photo; for "
                     "yes-or-no traits they are the change from no to yes.",
            "caps": "Entered as log2(1 + caps), so each odds ratio step is a doubling of caps.",
            "big_five": "Premier League, La Liga, Bundesliga, Serie A or Ligue 1 at call-up.",
            "market_value": "with_market_value fits the same model plus log2 of the player's Transfermarkt value, on "
                            "the players with a value set in the 12 months before the tournament "
                            "(data/raw/transfermarkt_wc2026_snapshot.csv). Players without one are mostly at clubs "
                            "outside the leagues Transfermarkt's data covers, so this model leaves out more of them.",
        },
        "coefficients": coefficients,
        "fit": fit,
        "with_market_value": {"coefficients": value_coefficients, "fit": value_fit},
        "shares": {
            "position": shares(players, lambda p: p["position_group"],
                               [(pos, lambda v, pos=pos: v == pos)
                                for pos in ("goalkeeper", "defender", "midfielder", "forward")]),
            "confederation": shares(players, lambda p: p["confederation"],
                                    [(c, lambda v, c=c: v == c) for c in ["UEFA"] + CONFEDERATIONS]),
            "caps": shares(players, lambda p: p["caps"],
                           [(band_label(lo, hi, "caps"), in_band(lo, hi)) for lo, hi in CAPS_BANDS]),
            "big_five_club": shares(players, lambda p: p["big_five_club"],
                                    [("big-five league club", lambda v: v), ("other club", lambda v: not v)]),
            "minutes": shares(players, lambda p: p["minutes"],
                              [(band_label(lo, hi, "minutes"), in_band(lo, hi)) for lo, hi in MINUTES_BANDS]),
            "market_value": shares(players, lambda p: value_band(p["market_value_eur"]),
                                   [(band, lambda v, band=band: v == band)
                                    for band in [value_band(lo * 1e6) for lo, _ in VALUE_BANDS_M]
                                    + ["no recent value"]]),
        },
        "curiosities": {
            "most_capped_without_photo": [
                {"player_id": p["player_id"], "display_name": p["display_name"], "team": p["team"], "caps": p["caps"]}
                for p in no_photo[:5]
            ],
            "most_valuable_without_photo": [
                {"player_id": p["player_id"], "display_name": p["display_name"], "team": p["team"],
                 "market_value_eur": int(p["market_value_eur"])}
                for p in priciest_without_photo[:5]
            ],
            "players_with_100_caps": len(centurions),
            "players_with_100_caps_with_photo": sum(p["has_photo"] for p in centurions),
            "highest_team_share": [{"team": t, "share": rounded(s)} for s, t in team_shares if s == team_shares[-1][0]],
            "lowest_team_share": [{"team": t, "share": rounded(s)} for s, t in team_shares if s == team_shares[0][0]],
        },
    }


def main() -> None:
    payload = build()
    print(f"Wrote {write_output('photo_correlates_2026', payload).relative_to(REPO_ROOT)}")
    print(f"{payload['about']['with_photo']} of {payload['about']['players']} players have a photo; "
          f"AUC {payload['fit']['auc_in_sample']} in sample, {payload['fit']['auc_cross_validated']} cross-validated")
    for title, model in (("All players", payload), ("With market value", payload["with_market_value"])):
        print(f"{title}: {model['fit']['players']} players, AUC {model['fit']['auc_in_sample']}, "
              f"{model['fit']['auc_cross_validated']} cross-validated")
        for c in model["coefficients"]:
            print(f"  {c['label']:44} OR {c['odds_ratio']:6} {c['odds_ratio_ci95']}  "
                  f"AME {c['average_marginal_effect_points']:6} points {c['average_marginal_effect_points_ci95']}  "
                  f"p {c['p_value']}")


if __name__ == "__main__":
    main()
