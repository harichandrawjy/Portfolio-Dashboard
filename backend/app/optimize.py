"""Mean-variance portfolio optimisation (Markowitz), long-only.

Pure, like `analytics.py`, and for the same reason: nothing here touches the
ORM, settings, or the network. Callers assemble aligned return series and get
numbers back.

The model
--------
Given expected returns mu and a covariance matrix Sigma, solve

    max_w  tau * wᵀmu - ½ wᵀSigma w      subject to  eᵀw = 1,  w >= 0

`tau` is the risk-tolerance parameter: 0 puts everything into minimum
variance, and raising it buys expected return with risk. Sweeping tau traces
the efficient frontier, which is why this one formulation is the only solver
here — the textbook's other two (maximise return under a variance budget,
minimise variance under a return floor) pick out points on that same curve.

Why long-only
-------------
The textbook formulation constrains only eᵀw = 1, which admits negative
weights — short positions. That has a closed-form solution and is two lines of
linear algebra, but this application cannot express the answer: a transaction
is a buy or a sell of shares actually held, and the schema enforces
`shares > 0`. An allocation telling you to short 40% of a ticker is not
advice this app can act on, so w >= 0 is part of the problem, not a garnish.

Why no solver dependency
------------------------
Adding w >= 0 turns the closed form into a quadratic program. The feasible set
{w >= 0, eᵀw = 1} is the probability simplex, the objective is convex, and
Euclidean projection onto a simplex has an exact O(n log n) algorithm — so
projected gradient descent converges to the GLOBAL optimum, no local minima to
worry about, in about forty lines. scipy would be a ~30 MB dependency and a
much longer image build on a 1 GB box, to solve a problem this shape does not
need it for.

What this is not
----------------
Estimates, not predictions. Sigma from five years of daily data is reasonably
stable; mu is mostly noise, and mean-variance optimisation is notoriously
sensitive to it — small changes in expected returns swing the weights hard.
That property is why the frontier is worth plotting and a single "optimal"
allocation is worth distrusting.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.analytics import TRADING_DAYS_PER_YEAR

# Projected gradient stops when no weight moves by more than this in a step.
# Weights are rendered to whole percentage points, so 1e-9 is far past the
# point of visible difference and still cheap for the handful of assets a
# lazily-backfilled universe can offer.
_TOLERANCE = 1e-9
_MAX_ITERATIONS = 20_000


@dataclass(frozen=True)
class Allocation:
    """One point on the frontier: what to hold, and what it implies."""

    weights: dict[str, float]  # ticker -> weight, sums to 1
    expected_return: float  # annualised
    volatility: float  # annualised standard deviation
    tau: float  # the risk-tolerance that produced it


def project_to_simplex(v: Sequence[float]) -> np.ndarray:
    """Closest point to `v` on {w >= 0, sum(w) = 1}, in Euclidean distance.

    Exact, not iterative. Sort descending, find how many coordinates survive,
    subtract the resulting threshold from each and clip at zero (Duchi et al.,
    2008). This is what makes projected gradient exact here: every step lands
    back on the feasible set at its true nearest point, so the descent is
    solving the constrained problem rather than approximating it.
    """
    u = np.sort(np.asarray(v, dtype=float))[::-1]
    cumulative = np.cumsum(u)
    indices = np.arange(1, u.size + 1)
    # The largest k whose k-th sorted coordinate stays above the running mean.
    eligible = u - (cumulative - 1.0) / indices > 0
    k = int(np.nonzero(eligible)[0][-1]) + 1
    theta = (cumulative[k - 1] - 1.0) / k
    return np.maximum(np.asarray(v, dtype=float) - theta, 0.0)


def optimal_weights(
    mu: Sequence[float], cov: Sequence[Sequence[float]], tau: float
) -> np.ndarray:
    """Maximise tau*wᵀmu - ½wᵀΣw over the simplex.

    Projected gradient with a fixed step of 1/L, where L is the largest
    eigenvalue of Sigma — the objective's Lipschitz constant. That is the
    standard guaranteed-convergent step size for a convex quadratic, so the
    result does not depend on a hand-tuned learning rate.
    """
    mu_v = np.asarray(mu, dtype=float)
    sigma = np.asarray(cov, dtype=float)
    n = mu_v.size

    if n == 0:
        return np.zeros(0)
    if n == 1:
        return np.ones(1)

    # Lipschitz constant of the gradient. Sigma is symmetric PSD, so eigvalsh
    # is both correct and faster than the general eigenvalue routine. The
    # floor guards a degenerate all-zero covariance (identical flat series),
    # where any step size is fine but 1/0 is not.
    largest = float(np.max(np.linalg.eigvalsh(sigma)))
    step = 1.0 / largest if largest > 1e-12 else 1.0

    w = np.full(n, 1.0 / n)  # equal weight: feasible, and a neutral prior
    for _ in range(_MAX_ITERATIONS):
        gradient = sigma @ w - tau * mu_v  # of ½wᵀΣw - tau*wᵀmu
        nxt = project_to_simplex(w - step * gradient)
        if np.max(np.abs(nxt - w)) < _TOLERANCE:
            return nxt
        w = nxt
    return w


def covariance_matrix(
    returns_by_ticker: dict[str, Sequence[float]],
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Annualised (tickers, mean returns, covariance) from daily returns.

    Series must already be date-aligned and equal length — alignment is the
    caller's job, exactly as it is for `analytics.beta`, and a mismatch is a
    caller bug rather than a degenerate input, so it raises.

    Tickers come back sorted so the matrix ordering is deterministic; a
    caller reading weights by position rather than by name would otherwise be
    at the mercy of dict ordering.
    """
    tickers = sorted(returns_by_ticker)
    if not tickers:
        return [], np.zeros(0), np.zeros((0, 0))

    lengths = {len(returns_by_ticker[t]) for t in tickers}
    if len(lengths) != 1:
        raise ValueError(
            f"covariance requires aligned series; got lengths {sorted(lengths)}"
        )

    matrix = np.array([list(returns_by_ticker[t]) for t in tickers], dtype=float)
    # ddof=1: sample covariance, matching analytics.beta and _sample_std.
    daily_cov = np.cov(matrix, ddof=1) if matrix.shape[1] > 1 else np.zeros(
        (len(tickers), len(tickers))
    )
    daily_cov = np.atleast_2d(daily_cov)
    mean_daily = matrix.mean(axis=1)

    # Variance scales with time, standard deviation with its square root — so
    # the covariance matrix takes the full factor and volatility comes out
    # right when it is later square-rooted.
    return (
        tickers,
        mean_daily * TRADING_DAYS_PER_YEAR,
        daily_cov * TRADING_DAYS_PER_YEAR,
    )


def log_returns(closes: Sequence[float]) -> list[float]:
    """Continuously-compounded daily returns, ln(P_t / P_t-1).

    Differs from `analytics.daily_returns` by roughly -sigma^2/2 per period,
    which is the volatility drag: ln(1+r) = r - r^2/2 + ... So the annualised
    mean of these is the GEOMETRIC return — what a holder actually compounded
    — where the arithmetic mean of simple returns overstates it, badly for a
    volatile asset. On this data GOTO's arithmetic -33.5%/yr is -50.2%/yr
    geometric, a 16.8pp gap against a half-sigma-squared of 17.1pp.

    Pairs whose base is non-positive are skipped, matching daily_returns.
    """
    out: list[float] = []
    prev = None
    for c in closes:
        c = float(c)
        if prev is not None and prev > 0 and c > 0:
            out.append(math.log(c / prev))
        prev = c
    return out


def annualised_log_mean(returns_by_ticker: dict[str, Sequence[float]]) -> tuple[list[str], np.ndarray]:
    """(tickers, annualised mean log return). Sorted, like covariance_matrix."""
    tickers = sorted(returns_by_ticker)
    if not tickers:
        return [], np.zeros(0)
    mu = np.array(
        [float(np.mean(list(returns_by_ticker[t]))) for t in tickers]
    ) * TRADING_DAYS_PER_YEAR
    return tickers, mu


def annualised_market_return(market_closes: Sequence[float]) -> float:
    """Geometric annualised return of the benchmark over the window.

    CAGR, not the mean daily return scaled up. For a single series the
    geometric figure is what actually happened to a holder — arithmetic means
    overstate compounding growth — and it is far less swayed by one violent
    session than a mean is.
    """
    closes = [float(c) for c in market_closes if c]
    if len(closes) < 2 or closes[0] <= 0:
        return 0.0
    years = (len(closes) - 1) / TRADING_DAYS_PER_YEAR
    if years <= 0:
        return 0.0
    return (closes[-1] / closes[0]) ** (1.0 / years) - 1.0


def capm_expected_returns(
    returns_by_ticker: dict[str, Sequence[float]],
    market_returns: Sequence[float],
    risk_free_rate: float,
    market_return: float,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Expected returns from CAPM: (tickers, mu, betas).

        E[Ri] = Rf + Bi * (E[Rm] - Rf)

    Replaces the historical mean as the estimate of mu, and it is the single
    biggest improvement available to this model. Mean-variance weights are
    notoriously sensitive to mu, and a per-stock average over two years is
    mostly noise — which is why the historical version put a stock's entire
    two-year drawdown into its "expected" return and then allocated as if that
    would continue.

    CAPM estimates one thing per stock instead: beta, its sensitivity to the
    market. Beta is a regression slope over hundreds of paired observations
    and is far steadier than a mean. Every stock's expected return is then
    pinned to the same market figure, so the estimates move together rather
    than eight noisy numbers drifting independently.

    What it buys is stability, not clairvoyance. CAPM assumes only systematic
    risk is rewarded, which is a model of the world, not a measurement of it —
    a stock that fell for reasons unrelated to the market gets an expected
    return that ignores the fall entirely. That is the point, and also the
    assumption to distrust.

    Everything here is annualised, matching `covariance_matrix`. Mixing an
    annual mu with a daily Sigma is a real and easy mistake: it inflates every
    Sharpe-like ratio by about sqrt(252).
    """
    tickers = sorted(returns_by_ticker)
    if not tickers:
        return [], np.zeros(0), np.zeros(0)

    market = np.asarray(list(market_returns), dtype=float)
    betas = np.zeros(len(tickers))
    for i, ticker in enumerate(tickers):
        asset = np.asarray(list(returns_by_ticker[ticker]), dtype=float)
        if asset.size != market.size:
            raise ValueError(
                f"CAPM needs date-aligned series; {ticker} has {asset.size} "
                f"observations against the market's {market.size}"
            )
        market_var = float(np.var(market, ddof=1)) if market.size > 1 else 0.0
        if market_var <= 0:
            # A flat benchmark carries no systematic risk to be paid for, so
            # every asset collapses to the risk-free rate rather than dividing
            # by zero.
            betas[i] = 0.0
            continue
        betas[i] = float(np.cov(asset, market, ddof=1)[0][1] / market_var)

    mu = risk_free_rate + betas * (market_return - risk_free_rate)
    return tickers, mu, betas


def portfolio_stats(
    weights: Sequence[float],
    mu: Sequence[float],
    cov: Sequence[Sequence[float]],
) -> tuple[float, float]:
    """(expected return, volatility) for a weighting, both annualised."""
    w = np.asarray(weights, dtype=float)
    expected = float(w @ np.asarray(mu, dtype=float))
    variance = float(w @ np.asarray(cov, dtype=float) @ w)
    # Clamp: a tiny negative can fall out of floating-point on a near-singular
    # covariance, and sqrt of it would be nan rather than ~0.
    return expected, math.sqrt(max(variance, 0.0))


def efficient_frontier(
    returns_by_ticker: dict[str, Sequence[float]],
    points: int = 40,
    mu: Sequence[float] | None = None,
) -> list[Allocation]:
    """Trace the frontier by sweeping the risk-tolerance parameter.

    tau = 0 is the minimum-variance portfolio. Raising it walks up the curve
    until the whole allocation collapses into the single highest-return asset,
    which is where the frontier ends under a long-only constraint.

    The sweep is geometric rather than linear: almost all of the interesting
    curvature is at low tau, and a linear sweep spends most of its points on
    the straight tail.
    """
    tickers, historical_mu, cov = covariance_matrix(returns_by_ticker)
    if not tickers:
        return []

    # `mu` overrides the historical mean — CAPM, normally. Sigma always comes
    # from the realised returns: the covariance structure is what the data
    # measures well, and CAPM has nothing to say about it anyway.
    mu = historical_mu if mu is None else np.asarray(mu, dtype=float)
    if len(mu) != len(tickers):
        raise ValueError(
            f"mu has {len(mu)} entries for {len(tickers)} tickers"
        )

    if len(tickers) == 1:
        expected, vol = portfolio_stats([1.0], mu, cov)
        return [Allocation({tickers[0]: 1.0}, expected, vol, 0.0)]

    # Upper end of the sweep, scaled to the data: tau trades return against
    # variance, so the tau at which return dominates is set by their ratio.
    tau_max = frontier_tau_max(mu, cov)

    taus = [0.0] + [
        tau_max * (10 ** (i / (points - 2) * 2 - 2)) for i in range(points - 1)
    ]

    out: list[Allocation] = []
    for tau in taus:
        w = optimal_weights(mu, cov, tau)
        expected, vol = portfolio_stats(w, mu, cov)
        out.append(
            Allocation(
                weights={t: float(x) for t, x in zip(tickers, w)},
                expected_return=expected,
                volatility=vol,
                tau=tau,
            )
        )
    # Deduplicate on the plotted coordinates: the top of a long-only frontier
    # is a single asset, so the last several taus all land on the same point
    # and would otherwise stack invisible markers there.
    seen: set[tuple[int, int]] = set()
    unique: list[Allocation] = []
    for a in out:
        key = (round(a.volatility, 6), round(a.expected_return, 6))
        rounded = (int(key[0] * 1e6), int(key[1] * 1e6))
        if rounded in seen:
            continue
        seen.add(rounded)
        unique.append(a)
    return unique

# ---------------------------------------------------------------------------
# Picking a single portfolio off the frontier
# ---------------------------------------------------------------------------
#
# The textbook's three formulations — minimise risk, minimise risk for a target
# return, maximise risk-adjusted return — are three ways of naming a point on
# the SAME curve, so all three are selections rather than separate problems.
# One tau sweep answers them all, and they cannot disagree with each other.
#
# The alternative is what the reference implementation does: a separate
# constrained solve per question, plus 5000 more to draw the curve. That is
# both slower and a way for the "optimal" portfolio to end up somewhere the
# drawn frontier says is unreachable.


def sharpe_ratio_of(allocation: Allocation, risk_free_rate: float) -> float | None:
    """(return - Rf) / volatility. None when there is no volatility to divide by."""
    if allocation.volatility <= 1e-12:
        return None
    return (allocation.expected_return - risk_free_rate) / allocation.volatility


def select_min_risk(curve: Sequence[Allocation]) -> Allocation | None:
    """The leftmost point: least variance, whatever that costs in return."""
    return min(curve, key=lambda a: a.volatility) if curve else None


def select_max_sharpe(
    curve: Sequence[Allocation],
    mu: Sequence[float],
    cov: Sequence[Sequence[float]],
    tickers: Sequence[str],
    risk_free_rate: float,
) -> Allocation | None:
    """The tangency portfolio: best return per unit of risk.

    Found on the curve rather than by a separate optimisation, because the
    maximum-Sharpe portfolio provably lies ON the efficient frontier — nothing
    off it can have a better ratio, since for any interior point there is a
    frontier point with the same risk and more return.

    The sweep is a grid, so the best grid point is refined by bisecting tau
    against its neighbours. Without that the answer is only as precise as the
    spacing, which is coarse exactly where the curve bends hardest.
    """
    if not curve:
        return None

    scored = [(sharpe_ratio_of(a, risk_free_rate), a) for a in curve]
    scored = [(s, a) for s, a in scored if s is not None]
    if not scored:
        return None

    best_sharpe, best = max(scored, key=lambda pair: pair[0])
    taus = sorted(a.tau for a in curve)
    i = taus.index(best.tau)
    lo = taus[max(0, i - 1)]
    hi = taus[min(len(taus) - 1, i + 1)]

    # Golden-section on tau. The Sharpe ratio along the frontier is unimodal,
    # so this converges on the peak rather than a neighbouring shoulder.
    phi = (5 ** 0.5 - 1) / 2
    for _ in range(40):
        a1 = hi - phi * (hi - lo)
        a2 = lo + phi * (hi - lo)
        s1 = _sharpe_at(a1, mu, cov, tickers, risk_free_rate)
        s2 = _sharpe_at(a2, mu, cov, tickers, risk_free_rate)
        if (s1 or -1e9) < (s2 or -1e9):
            lo = a1
        else:
            hi = a2
        if hi - lo < 1e-9:
            break

    refined = _allocation_at((lo + hi) / 2, mu, cov, tickers)
    refined_sharpe = sharpe_ratio_of(refined, risk_free_rate)
    if refined_sharpe is not None and refined_sharpe > best_sharpe:
        return refined
    return best


def select_for_target_return(
    target: float,
    mu: Sequence[float],
    cov: Sequence[Sequence[float]],
    tickers: Sequence[str],
    tau_max: float,
) -> Allocation | None:
    """Least risk among portfolios reaching `target` expected return.

    Bisects tau rather than adding the return as a second equality
    constraint. Expected return rises monotonically with tau along the
    frontier, so bisection lands on the same portfolio a constrained solve
    would — and it reuses the one solver instead of needing a projection onto
    {w >= 0, sum w = 1, wᵀmu = target}, which has no cheap exact form.

    Returns None when the target is out of reach: long-only cannot exceed the
    best single asset, and cannot go below the minimum-variance portfolio's
    return without deliberately choosing a worse portfolio.
    """
    lo_alloc = _allocation_at(0.0, mu, cov, tickers)
    hi_alloc = _allocation_at(tau_max, mu, cov, tickers)
    if target > hi_alloc.expected_return + 1e-12:
        return None  # beyond the best the holdings can do
    if target <= lo_alloc.expected_return:
        return lo_alloc  # already satisfied at minimum variance

    lo, hi = 0.0, tau_max
    for _ in range(60):
        mid = (lo + hi) / 2
        alloc = _allocation_at(mid, mu, cov, tickers)
        if alloc.expected_return < target:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return _allocation_at(hi, mu, cov, tickers)


def _allocation_at(
    tau: float,
    mu: Sequence[float],
    cov: Sequence[Sequence[float]],
    tickers: Sequence[str],
) -> Allocation:
    w = optimal_weights(mu, cov, tau)
    expected, vol = portfolio_stats(w, mu, cov)
    return Allocation(
        weights={t: float(x) for t, x in zip(tickers, w)},
        expected_return=expected,
        volatility=vol,
        tau=tau,
    )


def _sharpe_at(
    tau: float,
    mu: Sequence[float],
    cov: Sequence[Sequence[float]],
    tickers: Sequence[str],
    risk_free_rate: float,
) -> float | None:
    return sharpe_ratio_of(_allocation_at(tau, mu, cov, tickers), risk_free_rate)


def frontier_tau_max(mu: Sequence[float], cov: Sequence[Sequence[float]]) -> float:
    """The top of the tau sweep, exposed so selectors share the same range."""
    mu_v = np.asarray(mu, dtype=float)
    spread = float(np.max(mu_v) - np.min(mu_v))
    scale = float(np.max(np.diag(np.asarray(cov, dtype=float))))
    return (scale / spread) * 4.0 if spread > 1e-12 else 1.0
