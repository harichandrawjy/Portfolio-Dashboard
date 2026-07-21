"""Unit tests for realized P&L (average-cost). Hand-computed expectations."""

from app.pnl import realized_pnl


def test_no_sells_is_zero():
    assert realized_pnl([("BUY", 100, 1000, 0)]) == 0
    assert realized_pnl([]) == 0


def test_simple_gain():
    # buy 100 @ 1000, sell 100 @ 1200 -> (1200-1000)*100 = +20_000
    assert realized_pnl([("BUY", 100, 1000, 0), ("SELL", 100, 1200, 0)]) == 20_000


def test_fees_reduce_realized():
    # buy 100 @ 1000 fee 5000 -> cost basis 105_000, avg 1050/sh
    # sell 100 @ 1200 fee 3000 -> proceeds 120_000 - 3000 = 117_000
    # realized = 117_000 - 100*1050 = 117_000 - 105_000 = +12_000
    assert realized_pnl([("BUY", 100, 1000, 5000), ("SELL", 100, 1200, 3000)]) == 12_000


def test_partial_sell_keeps_average():
    # buy 100 @ 1000, buy 100 @ 1400 -> 200 sh, cost 240_000, avg 1200
    # sell 100 @ 1500 -> realized = (1500-1200)*100 = +30_000
    # remaining 100 sh cost 120_000; sell 100 @ 1000 -> (1000-1200)*100 = -20_000
    # total realized = 30_000 - 20_000 = +10_000
    trades = [
        ("BUY", 100, 1000, 0),
        ("BUY", 100, 1400, 0),
        ("SELL", 100, 1500, 0),
        ("SELL", 100, 1000, 0),
    ]
    assert realized_pnl(trades) == 10_000


def test_realized_loss():
    # buy 100 @ 2000, sell 100 @ 1500 -> (1500-2000)*100 = -50_000
    assert realized_pnl([("BUY", 100, 2000, 0), ("SELL", 100, 1500, 0)]) == -50_000


def test_rebuy_after_full_exit_resets_basis():
    # buy 100 @ 1000, sell all @ 1200 (+20_000), then buy 100 @ 5000 and
    # sell @ 5100 -> +10_000. The high re-buy must not taint the first cycle.
    trades = [
        ("BUY", 100, 1000, 0),
        ("SELL", 100, 1200, 0),
        ("BUY", 100, 5000, 0),
        ("SELL", 100, 5100, 0),
    ]
    assert realized_pnl(trades) == 30_000
