"""The analyses in scripts/analysis: the Elo formula, the ordered logit, and
whether the committed outputs in data/processed/analysis still follow from the
code and the data.

When an output test fails after a data change, rerun
    python scripts/analysis/team_strength.py
    python scripts/analysis/win_factors.py
    python scripts/analysis/photo_correlates.py
in that order and commit the outputs.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "scripts" / "analysis"
sys.path.insert(0, str(ANALYSIS))  # the scripts import each other by name


def load_script(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ANALYSIS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


ol = load_script("ordered_logit")
strength = load_script("team_strength")
win_factors = load_script("win_factors")
photos = load_script("photo_correlates")


# Elo ---------------------------------------------------------------------------


def test_expected_result() -> None:
    assert strength.expected_result(0) == 0.5
    assert strength.expected_result(400) == pytest.approx(10 / 11)
    assert strength.expected_result(-200) == pytest.approx(1 - strength.expected_result(200))


def test_goal_margin_multiplier() -> None:
    assert [strength.margin_multiplier(n) for n in (0, 1, -1, 2, 3, 4)] == [1.0, 1.0, 1.0, 1.5, 1.75, 1.875]


def test_k_factor_by_match_type() -> None:
    assert strength.k_factor("FIFA World Cup") == 60
    assert strength.k_factor("UEFA Euro") == 50
    assert strength.k_factor("FIFA World Cup qualification") == 40
    assert strength.k_factor("UEFA Nations League") == 40
    assert strength.k_factor("Friendly") == 20
    assert strength.k_factor("Gulf Cup") == 30


def test_rating_change() -> None:
    # Equal teams, a 2-0 home win in a friendly: K 20, margin 1.5, and the home
    # side was expected to score 0.640 because of its 100 points.
    expected = 20 * 1.5 * (1 - 1 / (10 ** (-100 / 400) + 1))
    assert strength.rating_change(1500, 1500, 2, 0, "Friendly", neutral=False) == pytest.approx(expected)
    # On neutral ground a draw between equal teams moves nothing.
    assert strength.rating_change(1500, 1500, 1, 1, "FIFA World Cup", neutral=True) == 0
    # The weaker side gains from a draw.
    assert strength.rating_change(1600, 1800, 0, 0, "FIFA World Cup", neutral=True) > 0


def test_the_snapshot_holds_the_tracker_matches_with_the_same_scores() -> None:
    rows, _ = strength.rate(strength.load_results())
    assert max(r["date"] for r in rows) == "2026-07-19"
    # world_cup_2026 raises if a match is missing or a score disagrees.
    assert len(strength.world_cup_2026(rows)) == 104


# The ordered logit -----------------------------------------------------------


def simulated_matches(n: int = 400, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = np.column_stack([rng.normal(0, 2, n), rng.choice([-1.0, 0.0, 1.0], n)])
    P = ol.probabilities(X, np.array([0.5, 0.4]), 0.6)
    y = np.array([rng.choice(3, p=p) for p in P])
    return X, y


def test_probabilities_sum_to_one_and_ignore_team_order() -> None:
    X, _ = simulated_matches()
    P = ol.probabilities(X, np.array([0.5, 0.4]), 0.6)
    assert np.allclose(P.sum(axis=1), 1)
    assert (P > 0).all()
    assert np.allclose(ol.probabilities(-X, np.array([0.5, 0.4]), 0.6), P[:, ::-1])


def test_exact_score_matches_numerical_gradient() -> None:
    from statsmodels.tools.numdiff import approx_fprime

    X, y = simulated_matches()
    model = ol.SymmetricOrderedLogit(y, X)
    params = np.array([0.3, -0.2, np.log(0.7)])
    assert np.allclose(model.score(params), approx_fprime(params, model.loglike, centered=True), atol=1e-5)


def test_matches_statsmodels_ordered_model_on_both_orientations() -> None:
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    X, y = simulated_matches()
    fit = ol.fit(X, y, ["gap", "home"])
    both = OrderedModel(np.concatenate([y, 2 - y]), np.vstack([X, -X]), distr="logit")
    both = both.fit(method="bfgs", disp=False, maxiter=1000)
    thresholds = both.model.transform_threshold_params(both.params)[1:-1]
    assert np.allclose(fit.beta, both.params[:2], atol=1e-4)
    assert np.allclose(thresholds, [-fit.cut, fit.cut], atol=1e-4)
    assert fit.loglike == pytest.approx(both.llf / 2, abs=1e-6)


def test_scoring_rules_on_a_sure_forecast() -> None:
    P = np.array([[0.0, 0.0, 1.0]])
    assert ol.ranked_probability_score(P, np.array([2]))[0] == 0
    assert ol.ranked_probability_score(P, np.array([0]))[0] == 1  # the worst possible
    assert ol.ranked_probability_score(P, np.array([1]))[0] == 0.5  # a draw is closer than a loss
    assert ol.brier_score(P, np.array([2]))[0] == 0


# Committed outputs -------------------------------------------------------------


def assert_same(actual, expected, path: str = "") -> None:
    """Equal, allowing the last rounded digit of a float to differ."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), f"{path}: keys differ"
        for key in expected:
            assert_same(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{path}: lengths differ"
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert_same(a, e, f"{path}[{i}]")
    elif isinstance(expected, float) and not isinstance(actual, bool):
        assert isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=1e-6, abs_tol=2e-4), \
            f"{path}: {actual} != {expected}"
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


def committed(name: str) -> dict:
    return json.loads((REPO / "data/processed/analysis" / f"{name}.json").read_text(encoding="utf-8"))


def regenerated(payload: dict) -> dict:
    return json.loads(json.dumps(payload))  # tuples to lists, as written


def test_team_strength_and_forecasts_are_current() -> None:
    team_strength, forecasts = strength.build()
    assert_same(regenerated(team_strength), committed("team_strength_2026"), "team_strength_2026")
    assert_same(regenerated(forecasts), committed("match_forecasts_2026"), "match_forecasts_2026")


def test_win_factors_are_current() -> None:
    assert_same(regenerated(win_factors.build()), committed("win_factors_2026"), "win_factors_2026")


def test_photo_correlates_are_current() -> None:
    assert_same(regenerated(photos.build()), committed("photo_correlates_2026"), "photo_correlates_2026")


def test_forecasts_cover_every_match_once() -> None:
    forecasts = committed("match_forecasts_2026")["matches"]
    matches = json.loads((REPO / "data/processed/app_exports/matches.json").read_text(encoding="utf-8"))
    assert sorted(f["match_id"] for f in forecasts) == sorted(m["match_id"] for m in matches)
    for f in forecasts:
        assert f["p_home_win"] + f["p_draw"] + f["p_away_win"] == pytest.approx(1, abs=1e-3)
