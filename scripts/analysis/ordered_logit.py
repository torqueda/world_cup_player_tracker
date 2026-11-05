"""
Win, draw or loss as a symmetric ordered logit, and the scoring rules used to
judge forecasts of them.

A match is seen from its first-named team. With eta = x @ beta,

    P(win)  = F(eta - c)
    P(loss) = F(-eta - c)
    P(draw) = 1 - P(win) - P(loss)

where F is the logistic function and c > 0 sets how often equal teams draw.
Swapping the two teams flips the sign of x and swaps the win and loss
probabilities, so the order the teams are listed in does not matter. That is
why the model has one cut point and no intercept, and why every feature is a
difference between the two teams (first minus second) or the home flag: +1
when the first team plays at home, -1 when the second does, 0 on neutral
ground.

This is the usual ordered logit (statsmodels' OrderedModel) with its two cut
points tied together as -c and +c. Fitting OrderedModel to every match seen
from both sides gives the same estimates, which tests/test_analyses.py checks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit, log_expit
from scipy.stats import chi2, norm
from statsmodels.base.model import GenericLikelihoodModel
from statsmodels.tools.numdiff import approx_fprime

LOSS, DRAW, WIN = 0, 1, 2
OUTCOME_NAMES = ("loss", "draw", "win")


def outcome(goals_for: int, goals_against: int) -> int:
    """The first team's result. A shootout counts as a draw."""
    return WIN if goals_for > goals_against else DRAW if goals_for == goals_against else LOSS


def probabilities(X: np.ndarray, beta: np.ndarray, cut: float) -> np.ndarray:
    """Rows of [P(loss), P(draw), P(win)] for the first team."""
    eta = np.asarray(X, dtype=float) @ np.asarray(beta, dtype=float)
    p_win = expit(eta - cut)
    p_loss = expit(-eta - cut)
    return np.column_stack([p_loss, 1.0 - p_win - p_loss, p_win])


class SymmetricOrderedLogit(GenericLikelihoodModel):
    """The model above. The last parameter is log(c), which keeps c positive."""

    def __init__(self, endog, exog, **kwds):
        super().__init__(endog, exog, extra_params_names=["log_cut"], **kwds)
        # No intercept: every feature is a slope and the cut point is the extra
        # parameter. (GenericLikelihoodModel otherwise assumes a constant.)
        self.k_constant = 0
        self.df_model = float(np.linalg.matrix_rank(self.exog))
        self.df_resid = float(self.exog.shape[0] - self.df_model - self.k_extra)

    def loglikeobs(self, params: np.ndarray) -> np.ndarray:
        beta, cut = params[:-1], np.exp(params[-1])
        eta = self.exog @ beta
        y = np.asarray(self.endog, dtype=int)
        out = np.empty(len(y))
        win, loss, draw = y == WIN, y == LOSS, y == DRAW
        out[win] = log_expit(eta[win] - cut)
        out[loss] = log_expit(-eta[loss] - cut)
        p_draw = 1.0 - expit(eta[draw] - cut) - expit(-eta[draw] - cut)
        out[draw] = np.log(np.clip(p_draw, 1e-300, None))
        return out

    def score_obs(self, params: np.ndarray) -> np.ndarray:
        beta, cut = params[:-1], np.exp(params[-1])
        eta = self.exog @ beta
        y = np.asarray(self.endog, dtype=int)
        a, b = eta - cut, -eta - cut  # arguments of P(win) and P(loss)
        fa, fb = expit(a), expit(b)
        d_eta = np.empty(len(y))
        d_log_cut = np.empty(len(y))
        win, loss, draw = y == WIN, y == LOSS, y == DRAW
        d_eta[win] = 1.0 - fa[win]
        d_log_cut[win] = -(1.0 - fa[win]) * cut
        d_eta[loss] = -(1.0 - fb[loss])
        d_log_cut[loss] = -(1.0 - fb[loss]) * cut
        dens_a, dens_b = fa * (1.0 - fa), fb * (1.0 - fb)
        p_draw = np.clip(1.0 - fa - fb, 1e-300, None)
        d_eta[draw] = (dens_b[draw] - dens_a[draw]) / p_draw[draw]
        d_log_cut[draw] = cut * (dens_a[draw] + dens_b[draw]) / p_draw[draw]
        return np.column_stack([self.exog * d_eta[:, None], d_log_cut])

    def score(self, params: np.ndarray) -> np.ndarray:
        return self.score_obs(params).sum(axis=0)

    def hessian(self, params: np.ndarray) -> np.ndarray:
        # Differences of the exact score: one step of numerical error, not two.
        H = approx_fprime(params, self.score, centered=True)
        return (H + H.T) / 2


@dataclass
class Fit:
    names: list[str]
    beta: np.ndarray
    cut: float
    bse: np.ndarray  # standard errors of beta
    loglike: float
    n: int

    def predict(self, X: np.ndarray) -> np.ndarray:
        return probabilities(X, self.beta, self.cut)

    def coefficients(self, scale: dict[str, float] | None = None) -> list[dict]:
        """Each coefficient as an odds ratio with its 95% interval.

        scale gives the unit to report per feature (for example 10 caps when
        the feature is in caps): the coefficient is multiplied by it first.
        """
        rows = []
        for name, b, se in zip(self.names, self.beta, self.bse):
            unit = (scale or {}).get(name, 1.0)
            rows.append({
                "feature": name,
                "per": unit,
                "coefficient": b * unit,
                "std_error": se * unit,
                "odds_ratio": float(np.exp(b * unit)),
                "odds_ratio_ci95": [float(np.exp((b - 1.96 * se) * unit)), float(np.exp((b + 1.96 * se) * unit))],
                "p_value": float(2 * norm.sf(abs(b / se))),
            })
        return rows


def fit(X: np.ndarray, y: np.ndarray, names: list[str], start: np.ndarray | None = None) -> Fit:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    model = SymmetricOrderedLogit(y, X)
    model.exog_names[: X.shape[1]] = names
    if start is None:
        start = np.concatenate([np.zeros(X.shape[1]), [np.log(0.5)]])
    result = model.fit(start_params=start, method="newton", maxiter=100, disp=False)
    if not result.mle_retvals["converged"] or np.abs(model.score(result.params)).max() > 1e-6:
        raise RuntimeError(f"ordered logit did not converge on {names}")
    params, bse = np.asarray(result.params), np.asarray(result.bse)
    return Fit(names, params[:-1], float(np.exp(params[-1])), bse[:-1], float(result.llf), len(y))


def likelihood_ratio_p(smaller: Fit, larger: Fit) -> float:
    """p-value of the likelihood-ratio test of a nested model against a larger one."""
    df = len(larger.beta) - len(smaller.beta)
    return float(chi2.sf(2.0 * (larger.loglike - smaller.loglike), df))


# Scoring rules, per match ------------------------------------------------------
#
# P has rows [P(loss), P(draw), P(win)]; y holds 0, 1 or 2. Lower is better
# for all but accuracy.


def ranked_probability_score(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    """RPS: the squared error of the cumulative forecast, which credits a forecast
    for putting probability next to the result (a draw is closer to a win than a
    loss is)."""
    observed = np.eye(3)[y]
    gap = np.cumsum(P, axis=1) - np.cumsum(observed, axis=1)
    return 0.5 * (gap[:, :2] ** 2).sum(axis=1)


def log_loss(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(P[np.arange(len(y)), y], 1e-15, None))


def brier_score(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    return ((P - np.eye(3)[y]) ** 2).sum(axis=1)


def accuracy(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    return (P.argmax(axis=1) == y).astype(float)


SCORES = {
    "ranked_probability_score": ranked_probability_score,
    "log_loss": log_loss,
    "brier_score": brier_score,
    "accuracy": accuracy,
}


def bootstrap_ci(values: np.ndarray, seed: int, resamples: int = 10_000) -> list[float]:
    """Percentile 95% interval of the mean, resampling matches."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(resamples, len(values)))
    means = np.asarray(values)[idx].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]
