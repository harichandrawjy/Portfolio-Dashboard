"""Mean-variance optimisation: properties, and cases with known answers.

The solver is projected gradient rather than a closed form, so "it returned
numbers" proves nothing. These check the things that would actually be wrong
if it were broken: feasibility, agreement with the analytic optimum where one
exists, and the qualitative behaviour the model is supposed to have.
"""

import math

import numpy as np
import pytest

from app.analytics import TRADING_DAYS_PER_YEAR
from app.optimize import (
    covariance_matrix,
    efficient_frontier,
    optimal_weights,
    portfolio_stats,
    project_to_simplex,
)


# ---------------------------------------------------------------------------
# the projection
# ---------------------------------------------------------------------------


def test_projection_leaves_points_already_on_the_simplex_alone():
    w = np.array([0.2, 0.3, 0.5])
    assert np.allclose(project_to_simplex(w), w)


def test_projection_lands_on_the_simplex_from_anywhere():
    for v in ([5.0, -2.0, 0.1], [-1.0, -1.0, -1.0], [0.0, 0.0, 100.0]):
        p = project_to_simplex(v)
        assert p.sum() == pytest.approx(1.0)
        assert (p >= 0).all()


def test_projection_is_the_nearest_such_point():
    """Spot-check against brute force on a coarse grid."""
    v = np.array([0.9, 0.2, -0.4])
    p = project_to_simplex(v)
    best = min(
        (
            np.array([a, b, 1 - a - b])
            for a in np.linspace(0, 1, 101)
            for b in np.linspace(0, 1 - a, 101)
        ),
        key=lambda c: np.sum((c - v) ** 2),
    )
    # The grid is coarse, so compare distances rather than coordinates.
    assert np.sum((p - v) ** 2) <= np.sum((best - v) ** 2) + 1e-6


# ---------------------------------------------------------------------------
# the optimiser
# ---------------------------------------------------------------------------


def test_weights_are_always_a_valid_long_only_allocation():
    mu = [0.10, 0.20, 0.05]
    cov = [[0.04, 0.01, 0.00], [0.01, 0.09, 0.00], [0.00, 0.00, 0.01]]
    for tau in (0.0, 0.5, 5.0, 100.0):
        w = optimal_weights(mu, cov, tau)
        assert w.sum() == pytest.approx(1.0)
        assert (w >= -1e-12).all(), f"tau={tau} produced a short position: {w}"


def test_zero_risk_tolerance_gives_the_minimum_variance_portfolio():
    """With tau=0 the objective is pure variance, which has a known answer.

    For uncorrelated assets the minimum-variance weights are proportional to
    the inverse of each variance — a textbook result, so it pins the solver
    against arithmetic rather than against itself.
    """
    variances = [0.04, 0.01, 0.25]
    cov = np.diag(variances)
    w = optimal_weights([0.1, 0.1, 0.1], cov, tau=0.0)

    inverse = np.array([1 / v for v in variances])
    expected = inverse / inverse.sum()
    assert np.allclose(w, expected, atol=1e-6)


def test_high_risk_tolerance_concentrates_on_the_best_asset():
    """Push tau far enough and return dominates variance entirely."""
    mu = [0.05, 0.30, 0.10]
    cov = [[0.04, 0.0, 0.0], [0.0, 0.05, 0.0], [0.0, 0.0, 0.02]]
    w = optimal_weights(mu, cov, tau=1e6)
    assert w[1] == pytest.approx(1.0, abs=1e-4)


def test_a_dominated_asset_gets_nothing():
    """Worse return AND worse variance, uncorrelated — no reason to hold it."""
    mu = [0.20, 0.02]
    cov = [[0.02, 0.0], [0.0, 0.30]]
    w = optimal_weights(mu, cov, tau=1.0)
    assert w[1] == pytest.approx(0.0, abs=1e-6)
    assert w[0] == pytest.approx(1.0, abs=1e-6)


def test_diversifies_across_negatively_correlated_assets():
    """The whole point of the model: correlation, not just variance.

    Two assets with identical mean and variance but strong negative
    correlation should be held together, because the pair is calmer than
    either alone.
    """
    mu = [0.10, 0.10]
    cov = [[0.04, -0.035], [-0.035, 0.04]]
    w = optimal_weights(mu, cov, tau=0.0)
    assert w == pytest.approx([0.5, 0.5], abs=1e-6)

    _, pair_vol = portfolio_stats(w, mu, cov)
    _, solo_vol = portfolio_stats([1.0, 0.0], mu, cov)
    assert pair_vol < solo_vol


def test_single_asset_is_fully_invested():
    assert optimal_weights([0.1], [[0.04]], tau=1.0) == pytest.approx([1.0])


def test_empty_input_returns_nothing_rather_than_raising():
    assert optimal_weights([], [], tau=1.0).size == 0


# ---------------------------------------------------------------------------
# covariance from return series
# ---------------------------------------------------------------------------


def test_covariance_annualises_and_orders_deterministically():
    daily = {
        "TLKM": [0.01, -0.01, 0.02, 0.00, -0.02],
        "BBCA": [0.02, -0.02, 0.01, 0.01, -0.01],
    }
    tickers, mu, cov = covariance_matrix(daily)

    assert tickers == ["BBCA", "TLKM"]  # sorted, not dict order
    expected_mu = np.mean(daily["BBCA"]) * TRADING_DAYS_PER_YEAR
    assert mu[0] == pytest.approx(expected_mu)

    manual = np.cov(np.array([daily["BBCA"], daily["TLKM"]]), ddof=1)
    assert np.allclose(cov, manual * TRADING_DAYS_PER_YEAR)


def test_covariance_rejects_misaligned_series():
    """A length mismatch is a caller bug, like analytics.beta — so it raises."""
    with pytest.raises(ValueError, match="aligned"):
        covariance_matrix({"A": [0.01, 0.02], "B": [0.01]})


def test_covariance_of_nothing_is_empty():
    tickers, mu, cov = covariance_matrix({})
    assert tickers == [] and mu.size == 0 and cov.size == 0


# ---------------------------------------------------------------------------
# the frontier
# ---------------------------------------------------------------------------


def _sample_returns() -> dict[str, list[float]]:
    rng = np.random.default_rng(7)
    n = 400
    market = rng.normal(0.0004, 0.010, n)
    return {
        "BBCA": (market * 0.9 + rng.normal(0.0002, 0.004, n)).tolist(),
        "TLKM": (market * 1.1 + rng.normal(0.0000, 0.006, n)).tolist(),
        "GOTO": (market * 1.6 + rng.normal(-0.0002, 0.015, n)).tolist(),
    }


def test_frontier_slopes_upward_and_is_all_feasible():
    curve = efficient_frontier(_sample_returns(), points=25)
    assert len(curve) >= 5

    for a in curve:
        assert sum(a.weights.values()) == pytest.approx(1.0)
        assert all(w >= -1e-9 for w in a.weights.values())
        assert a.volatility >= 0

    # More risk should buy more return, monotonically — that is what makes it
    # a frontier rather than a scatter.
    by_risk = sorted(curve, key=lambda a: a.volatility)
    returns = [a.expected_return for a in by_risk]
    assert returns == sorted(returns), "frontier doubles back on itself"


def test_frontier_starts_at_minimum_variance():
    curve = efficient_frontier(_sample_returns(), points=25)
    lowest = min(a.volatility for a in curve)
    assert curve[0].volatility == pytest.approx(lowest, abs=1e-9)
    assert curve[0].tau == 0.0


def test_no_frontier_point_beats_the_best_single_asset_on_return():
    """Long-only caps the frontier: you cannot out-return everything you hold."""
    data = _sample_returns()
    tickers, mu, _ = covariance_matrix(data)
    curve = efficient_frontier(data, points=25)
    assert max(a.expected_return for a in curve) <= float(np.max(mu)) + 1e-9


def test_frontier_of_one_asset_is_that_asset():
    curve = efficient_frontier({"BBCA": [0.01, -0.01, 0.02, 0.00]})
    assert len(curve) == 1
    assert curve[0].weights == {"BBCA": 1.0}


def test_frontier_of_nothing_is_empty():
    assert efficient_frontier({}) == []


def test_diversification_actually_lowers_risk_versus_equal_weight():
    """If the optimiser cannot beat naive 1/N, it is not doing anything."""
    data = _sample_returns()
    tickers, mu, cov = covariance_matrix(data)
    curve = efficient_frontier(data, points=25)

    equal = [1 / len(tickers)] * len(tickers)
    _, equal_vol = portfolio_stats(equal, mu, cov)
    assert curve[0].volatility <= equal_vol + 1e-12
    assert math.isfinite(curve[0].volatility)
