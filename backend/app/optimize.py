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
    returns_by_ticker: dict[str, Sequence[float]], points: int = 40
) -> list[Allocation]:
    """Trace the frontier by sweeping the risk-tolerance parameter.

    tau = 0 is the minimum-variance portfolio. Raising it walks up the curve
    until the whole allocation collapses into the single highest-return asset,
    which is where the frontier ends under a long-only constraint.

    The sweep is geometric rather than linear: almost all of the interesting
    curvature is at low tau, and a linear sweep spends most of its points on
    the straight tail.
    """
    tickers, mu, cov = covariance_matrix(returns_by_ticker)
    if not tickers:
        return []

    if len(tickers) == 1:
        expected, vol = portfolio_stats([1.0], mu, cov)
        return [Allocation({tickers[0]: 1.0}, expected, vol, 0.0)]

    # Upper end of the sweep, scaled to the data: tau trades return against
    # variance, so the tau at which return dominates is set by their ratio.
    spread = float(np.max(mu) - np.min(mu))
    scale = float(np.max(np.diag(cov)))
    tau_max = (scale / spread) * 4.0 if spread > 1e-12 else 1.0

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
