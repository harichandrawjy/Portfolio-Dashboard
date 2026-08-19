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
    capm_expected_returns,
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


# ---------------------------------------------------------------------------
# CAPM expected returns
# ---------------------------------------------------------------------------


def test_capm_matches_the_formula_by_hand():
    """E[Ri] = Rf + Bi(E[Rm] - Rf), checked against arithmetic."""
    market = [0.01, -0.01, 0.02, -0.02, 0.015, -0.005]
    # Exactly twice the market: beta must come out at 2.0.
    doubled = [2 * r for r in market]
    tickers, mu, betas = capm_expected_returns(
        {"LEVERED": doubled}, market, risk_free_rate=0.055, market_return=0.12
    )
    assert tickers == ["LEVERED"]
    assert betas[0] == pytest.approx(2.0, abs=1e-9)
    # 0.055 + 2 * (0.12 - 0.055) = 0.185
    assert mu[0] == pytest.approx(0.185, abs=1e-9)


def test_capm_beta_of_the_market_itself_is_one():
    market = [0.01, -0.01, 0.02, -0.02, 0.015]
    _, mu, betas = capm_expected_returns(
        {"INDEX": market}, market, risk_free_rate=0.05, market_return=0.11
    )
    assert betas[0] == pytest.approx(1.0, abs=1e-9)
    assert mu[0] == pytest.approx(0.11, abs=1e-9)  # collapses to E[Rm]


def test_capm_zero_beta_earns_the_risk_free_rate():
    """No market exposure means no risk premium, up or down."""
    market = [0.01, -0.01, 0.02, -0.02]
    flat = [0.003, 0.003, 0.003, 0.003]  # no covariance with anything
    _, mu, betas = capm_expected_returns(
        {"FLAT": flat}, market, risk_free_rate=0.055, market_return=0.12
    )
    assert betas[0] == pytest.approx(0.0, abs=1e-9)
    assert mu[0] == pytest.approx(0.055, abs=1e-9)


def test_capm_inverts_when_the_market_underperforms_cash():
    """A negative risk premium makes high beta a liability, not an asset.

    This is not a defect — it is the model being consistent. It matters
    because it flips the frontier: the highest-return end becomes the LOWEST
    beta holding rather than the highest. Pinned so the behaviour is a
    decision rather than a surprise.
    """
    market = [0.01, -0.01, 0.02, -0.02, 0.015, -0.005]
    _, mu, betas = capm_expected_returns(
        {"HIGH": [2 * r for r in market], "LOW": [0.5 * r for r in market]},
        market,
        risk_free_rate=0.055,
        market_return=-0.075,  # market below cash
    )
    high = mu[list(sorted({"HIGH", "LOW"})).index("HIGH")]
    low = mu[list(sorted({"HIGH", "LOW"})).index("LOW")]
    assert high < low, "with a negative premium, more beta must mean less return"


def test_capm_rejects_misaligned_market_series():
    with pytest.raises(ValueError, match="aligned"):
        capm_expected_returns(
            {"A": [0.01, 0.02, 0.03]}, [0.01, 0.02], 0.05, 0.10
        )


def test_annualised_market_return_is_geometric():
    """CAGR, not the arithmetic mean scaled up."""
    from app.optimize import annualised_market_return

    # Exactly one year of sessions, doubling in value.
    closes = [100.0] * 1
    closes = [100.0 * (2 ** (i / TRADING_DAYS_PER_YEAR)) for i in range(TRADING_DAYS_PER_YEAR + 1)]
    assert annualised_market_return(closes) == pytest.approx(1.0, abs=1e-6)
    assert annualised_market_return([100.0]) == 0.0
    assert annualised_market_return([]) == 0.0


def test_frontier_accepts_a_mu_override():
    """Sigma always comes from the data; only mu is substitutable."""
    data = _sample_returns()
    tickers, hist_mu, _ = covariance_matrix(data)
    flat = [0.10] * len(tickers)  # every asset identical on return
    curve = efficient_frontier(data, points=12, mu=flat)
    assert curve
    # With identical expected returns, no allocation can beat another on
    # return, so the curve collapses to the minimum-variance point.
    assert all(
        a.expected_return == pytest.approx(0.10, abs=1e-9) for a in curve
    )


def test_frontier_rejects_a_mu_of_the_wrong_length():
    with pytest.raises(ValueError, match="entries"):
        efficient_frontier(_sample_returns(), points=5, mu=[0.1, 0.2])


# ---------------------------------------------------------------------------
# selecting a single portfolio: the textbook's three formulations
# ---------------------------------------------------------------------------


def _setup():
    data = _sample_returns()
    tickers, mu, cov = covariance_matrix(data)
    curve = efficient_frontier(data, points=40)
    return data, tickers, mu, cov, curve


def test_min_risk_is_the_leftmost_frontier_point():
    from app.optimize import select_min_risk

    _, _, _, _, curve = _setup()
    pick = select_min_risk(curve)
    assert pick.volatility == pytest.approx(min(a.volatility for a in curve))
    assert pick.tau == 0.0


def test_max_sharpe_beats_every_point_on_the_curve():
    """The tangency portfolio must not be beaten by any sampled allocation."""
    from app.optimize import select_max_sharpe, sharpe_ratio_of

    _, tickers, mu, cov, curve = _setup()
    rf = 0.055
    pick = select_max_sharpe(curve, mu, cov, tickers, rf)
    best = sharpe_ratio_of(pick, rf)
    for a in curve:
        s = sharpe_ratio_of(a, rf)
        if s is not None:
            assert s <= best + 1e-9, "a grid point beat the refined tangency"


def test_max_sharpe_sits_between_min_variance_and_max_return():
    """It is a frontier point, so it cannot be off either end."""
    from app.optimize import select_max_sharpe

    _, tickers, mu, cov, curve = _setup()
    pick = select_max_sharpe(curve, mu, cov, tickers, 0.055)
    assert min(a.volatility for a in curve) - 1e-9 <= pick.volatility
    assert pick.volatility <= max(a.volatility for a in curve) + 1e-9
    assert sum(pick.weights.values()) == pytest.approx(1.0)
    assert all(w >= -1e-9 for w in pick.weights.values())


def test_target_return_is_hit_and_is_the_cheapest_way_to_hit_it():
    from app.optimize import frontier_tau_max, select_for_target_return

    _, tickers, mu, cov, curve = _setup()
    tau_max = frontier_tau_max(mu, cov)
    lo = min(a.expected_return for a in curve)
    hi = max(a.expected_return for a in curve)
    target = lo + 0.6 * (hi - lo)

    pick = select_for_target_return(target, mu, cov, tickers, tau_max)
    assert pick is not None
    assert pick.expected_return == pytest.approx(target, abs=1e-6)

    # Nothing on the curve reaches that return with less risk.
    for a in curve:
        if a.expected_return >= target - 1e-9:
            assert a.volatility >= pick.volatility - 1e-6


def test_target_return_beyond_reach_returns_nothing():
    """Long-only cannot beat the best single asset, so say so rather than lie."""
    from app.optimize import frontier_tau_max, select_for_target_return

    _, tickers, mu, cov, _ = _setup()
    unreachable = float(np.max(mu)) + 1.0
    assert (
        select_for_target_return(
            unreachable, mu, cov, tickers, frontier_tau_max(mu, cov)
        )
        is None
    )


def test_target_below_minimum_variance_returns_the_minimum_variance_portfolio():
    """Asking for less than the calmest portfolio earns is already satisfied."""
    from app.optimize import frontier_tau_max, select_for_target_return, select_min_risk

    _, tickers, mu, cov, curve = _setup()
    floor = select_min_risk(curve)
    pick = select_for_target_return(
        floor.expected_return - 0.05, mu, cov, tickers, frontier_tau_max(mu, cov)
    )
    assert pick.volatility == pytest.approx(floor.volatility, abs=1e-9)


def test_sharpe_ratio_handles_a_riskless_allocation():
    from app.optimize import sharpe_ratio_of
    from app.optimize import Allocation

    flat = Allocation(weights={"A": 1.0}, expected_return=0.05, volatility=0.0, tau=0.0)
    assert sharpe_ratio_of(flat, 0.055) is None


# ---------------------------------------------------------------------------
# log returns
# ---------------------------------------------------------------------------


def test_log_returns_are_the_log_of_the_price_ratio():
    from app.optimize import log_returns

    out = log_returns([100.0, 110.0, 99.0])
    assert out == pytest.approx([math.log(1.1), math.log(0.9)], abs=1e-12)


def test_log_returns_skip_non_positive_prices():
    """A zero or negative close has no defined log ratio."""
    from app.optimize import log_returns

    assert log_returns([100.0, 0.0, 50.0]) == []
    assert log_returns([]) == []
    assert log_returns([100.0]) == []


def test_log_return_is_below_simple_return_by_the_volatility_drag():
    """ln(1+r) = r - r^2/2 + ..., so the geometric mean trails the arithmetic.

    The gap is approximately sigma^2/2 — which is why a volatile holding's
    arithmetic "expected return" flatters it, and why the geometric figure is
    what a holder actually compounded.
    """
    from app.analytics import daily_returns
    from app.optimize import annualised_log_mean, covariance_matrix, log_returns

    rng = np.random.default_rng(11)
    closes = [100.0]
    for r in rng.normal(0.0005, 0.02, 2000):
        closes.append(closes[-1] * (1 + r))

    simple = {"X": daily_returns(closes)}
    logged = {"X": log_returns(closes)}
    _, arith, cov = covariance_matrix(simple)
    _, geo = annualised_log_mean(logged)

    drag = arith[0] - geo[0]
    assert drag > 0, "geometric must trail arithmetic"
    assert drag == pytest.approx(cov[0][0] / 2, rel=0.15)


def test_annualised_log_mean_sorts_like_covariance_matrix():
    """Both must agree on ordering or mu and Sigma would be mismatched."""
    from app.optimize import annualised_log_mean, covariance_matrix

    data = {"TLKM": [0.01, -0.02, 0.015], "BBCA": [0.005, 0.01, -0.008]}
    t1, mu = annualised_log_mean(data)
    t2, _, _ = covariance_matrix(data)
    assert t1 == t2 == ["BBCA", "TLKM"]
    assert mu.shape == (2,)


def test_annualised_log_mean_of_nothing_is_empty():
    from app.optimize import annualised_log_mean

    tickers, mu = annualised_log_mean({})
    assert tickers == [] and mu.size == 0
