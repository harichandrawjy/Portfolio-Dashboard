"""Unit tests for the pure analytics functions.

Every expected value is hand-computed in a comment next to the assertion —
if a formula changes, the arithmetic here is the contract it broke.
"""

import math

import pytest

from app.analytics import (
    annualized_volatility,
    beta,
    daily_returns,
    max_drawdown,
    sharpe_ratio,
    simple_return,
)

SQRT_252 = math.sqrt(252)  # 15.87450787...


# ---------------------------------------------------------------------------
# daily_returns / simple_return
# ---------------------------------------------------------------------------

def test_daily_returns():
    # 100 -> 110 is +10%; 110 -> 99 is -10%
    r = daily_returns([100, 110, 99])
    assert r == pytest.approx([0.10, -0.10])


def test_daily_returns_skips_zero_base():
    # the 0 -> 50 pair has no meaningful return and is skipped
    assert daily_returns([100, 0, 50]) == pytest.approx([-1.0])


def test_simple_return():
    # 100 -> 130 over the window = +30%
    assert simple_return([100, 120, 130]) == pytest.approx(0.30)


def test_simple_return_insufficient_data():
    assert simple_return([100]) is None
    assert simple_return([]) is None


# ---------------------------------------------------------------------------
# annualized_volatility
# ---------------------------------------------------------------------------

def test_annualized_volatility():
    # returns: +1%, -1%, +1%, -1%  ->  mean = 0
    # squared deviations: 4 x 0.0001 = 0.0004
    # sample variance (ddof=1): 0.0004 / 3 = 1.3333e-4
    # daily std: sqrt(1.3333e-4) = 0.0115470
    # annualized: 0.0115470 * sqrt(252) = 0.183303
    vol = annualized_volatility([0.01, -0.01, 0.01, -0.01])
    assert vol == pytest.approx(0.183303, abs=1e-5)


def test_volatility_insufficient_data():
    assert annualized_volatility([]) is None
    assert annualized_volatility([0.05]) is None


# ---------------------------------------------------------------------------
# sharpe_ratio
# ---------------------------------------------------------------------------

def test_sharpe_ratio():
    # returns: +2%, +1%, +3%  ->  mean = 0.02
    # deviations: 0, -0.01, +0.01 -> squared sum = 0.0002
    # sample std: sqrt(0.0002 / 2) = 0.01
    # rf_annual = 2.52% -> rf_daily = 0.0252 / 252 = 0.0001
    # sharpe = (0.02 - 0.0001) / 0.01 * sqrt(252)
    #        = 1.99 * 15.874508 = 31.590270
    s = sharpe_ratio([0.02, 0.01, 0.03], risk_free_annual=0.0252)
    assert s == pytest.approx(31.590270, abs=1e-4)


def test_sharpe_zero_variance_is_none():
    # constant returns: std = 0, ratio undefined
    assert sharpe_ratio([0.01, 0.01, 0.01], risk_free_annual=0.055) is None


# ---------------------------------------------------------------------------
# max_drawdown
# ---------------------------------------------------------------------------

def test_max_drawdown():
    # peak 120 -> trough 90: 90/120 - 1 = -25%
    # new peak 130 -> trough 80: 80/130 - 1 = -38.4615%   <- the max
    dd = max_drawdown([100, 120, 90, 130, 80])
    assert dd == pytest.approx(-0.384615, abs=1e-6)


def test_max_drawdown_monotonic_rise_is_zero():
    assert max_drawdown([1, 2, 3]) == 0.0


def test_max_drawdown_insufficient_data():
    assert max_drawdown([100]) is None


# ---------------------------------------------------------------------------
# beta
# ---------------------------------------------------------------------------

def test_beta_of_doubled_series_is_two():
    # asset moves exactly 2x the benchmark every day:
    # cov(2b, b) = 2*var(b), so beta = 2
    bench = [0.01, -0.01, 0.02, 0.00]
    asset = [0.02, -0.02, 0.04, 0.00]
    assert beta(asset, bench) == pytest.approx(2.0)


def test_beta_of_benchmark_with_itself_is_one():
    bench = [0.01, -0.02, 0.015, 0.005]
    assert beta(bench, bench) == pytest.approx(1.0)


def test_beta_flat_benchmark_is_none():
    # zero benchmark variance: beta undefined
    assert beta([0.01, 0.02, 0.03], [0.01, 0.01, 0.01]) is None


def test_beta_misaligned_series_raises():
    # unequal lengths are a caller bug, not missing data
    with pytest.raises(ValueError):
        beta([0.01, 0.02], [0.01])
