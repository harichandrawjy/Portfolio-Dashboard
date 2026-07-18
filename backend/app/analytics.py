"""Pure analytics over daily value/return series.

Every function here is deliberately ignorant of WHAT the series represents:
a portfolio's daily value or a single stock's closing prices behave
identically. The per-stock detail pages (Step 9) reuse these functions
unchanged — that reuse is the reason this module must stay pure: no ORM,
no settings, no I/O.

Conventions
-----------
- "values"  : positive daily levels (prices, portfolio values), oldest first
- "returns" : simple daily returns, r_i = v_i / v_{i-1} - 1
- Insufficient or degenerate input returns None instead of raising —
  callers render None as "—". Only a caller *bug* (misaligned series
  lengths in beta) raises.
- Annualization uses 252 trading days, the industry convention. IDX's
  actual calendar has ~247 sessions/year; the difference is negligible
  next to estimation noise.
"""

import math
from collections.abc import Sequence

TRADING_DAYS_PER_YEAR = 252


def daily_returns(values: Sequence[float]) -> list[float]:
    """Simple daily returns: r_i = v_i / v_{i-1} - 1.

    Pairs whose base value is zero are skipped (a zero level has no
    meaningful return off it).
    """
    out: list[float] = []
    for prev, cur in zip(values, values[1:]):
        if prev:
            out.append(cur / prev - 1)
    return out


def simple_return(values: Sequence[float]) -> float | None:
    """Total simple return over the whole window: v_end / v_start - 1."""
    if len(values) < 2 or not values[0]:
        return None
    return values[-1] / values[0] - 1


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _sample_std(xs: Sequence[float]) -> float | None:
    """Sample standard deviation (ddof=1). None below two observations."""
    n = len(xs)
    if n < 2:
        return None
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def annualized_volatility(
    returns: Sequence[float], trading_days: int = TRADING_DAYS_PER_YEAR
) -> float | None:
    """std(daily returns) * sqrt(trading_days)."""
    std = _sample_std(list(returns))
    if std is None:
        return None
    return std * math.sqrt(trading_days)


def sharpe_ratio(
    returns: Sequence[float],
    risk_free_annual: float,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> float | None:
    """(mean(r) - rf_daily) / std(r) * sqrt(trading_days).

    Risk-free assumption: `risk_free_annual` is an annual rate (the app
    passes Bank Indonesia's policy rate from config). It is de-annualized
    by simple division, rf_daily = rf_annual / trading_days — the standard
    approximation; the geometric alternative differs by ~1e-6 daily, far
    below estimation noise.
    """
    rs = list(returns)
    std = _sample_std(rs)
    if std is None or std == 0:
        return None
    rf_daily = risk_free_annual / trading_days
    return (_mean(rs) - rf_daily) / std * math.sqrt(trading_days)


def max_drawdown(values: Sequence[float]) -> float | None:
    """Largest peak-to-trough decline, as a negative fraction.

    -0.25 means the series at some point stood 25% below its prior peak.
    A monotonically rising series has a drawdown of 0.0.
    """
    if len(values) < 2:
        return None
    peak: float | None = None
    worst = 0.0
    for v in values:
        if peak is None or v > peak:
            peak = v
        elif peak > 0:
            worst = min(worst, v / peak - 1)
    return worst


def beta(
    asset_returns: Sequence[float], benchmark_returns: Sequence[float]
) -> float | None:
    """cov(asset, benchmark) / var(benchmark), sample statistics (ddof=1).

    The two series must be date-aligned and equal length — alignment is the
    caller's job, and a length mismatch is a caller bug, so it raises
    rather than returning None.
    """
    a = list(asset_returns)
    b = list(benchmark_returns)
    if len(a) != len(b):
        raise ValueError(
            f"beta requires aligned series; got {len(a)} vs {len(b)} points"
        )
    n = len(a)
    if n < 2:
        return None
    ma, mb = _mean(a), _mean(b)
    var_b = sum((y - mb) ** 2 for y in b) / (n - 1)
    if var_b == 0:
        return None
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1)
    return cov / var_b
