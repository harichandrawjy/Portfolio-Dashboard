"""Back-adjusting prices across corporate actions Yahoo never flagged.

Real case: PACK traded ~3670 and later ~226 with no split recorded and
auto_adjust returning identical data, so the raw series showed a cliff and
a fictitious ~94% loss.
"""

from datetime import date

from app.sync.prices import adjust_corporate_actions


def _bar(day: int, close: int, volume: int | None = 1000) -> dict:
    return {
        "trade_date": date(2026, 7, day),
        "open": close, "high": close, "low": close,
        "close": close, "volume": volume,
    }


def test_ordinary_volatility_is_left_alone():
    # a hard but legal IDX session (-25%) must not be treated as an action
    rows = [_bar(1, 1000), _bar(2, 750), _bar(3, 900)]
    assert adjust_corporate_actions(rows) == rows


def test_split_back_adjusts_earlier_bars():
    # 4:1 split between day 2 and day 3
    rows = [_bar(1, 4000), _bar(2, 4400), _bar(3, 1100), _bar(4, 1200)]
    out = adjust_corporate_actions(rows)
    # pre-split bars rescaled onto the post-split basis (x0.25)
    assert [r["close"] for r in out] == [1000, 1100, 1100, 1200]
    # post-split bars untouched
    assert out[2]["close"] == 1100 and out[3]["close"] == 1200
    # volume moves inversely: more shares after a split
    assert out[0]["volume"] == 4000 and out[3]["volume"] == 1000


def test_pack_style_collapse_is_adjusted():
    rows = [_bar(1, 3670), _bar(2, 3750), _bar(3, 226), _bar(4, 224)]
    out = adjust_corporate_actions(rows)
    closes = [r["close"] for r in out]
    # the cliff is gone: no adjacent pair moves more than a legal session
    for prev, cur in zip(closes, closes[1:]):
        assert 0.55 < cur / prev < 1.8
    assert closes[-2:] == [226, 224]  # recent bars stay as reported


def test_multiple_actions_compound():
    # 2:1 then another 2:1 -> earliest bars scaled by 0.25
    rows = [_bar(1, 4000), _bar(2, 2000), _bar(3, 1000)]
    assert [r["close"] for r in adjust_corporate_actions(rows)] == [1000, 1000, 1000]


def test_short_or_empty_series():
    assert adjust_corporate_actions([]) == []
    one = [_bar(1, 500)]
    assert adjust_corporate_actions(one) == one
