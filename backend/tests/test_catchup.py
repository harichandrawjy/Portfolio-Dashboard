"""Startup catch-up: which trading day's bar should already exist.

Reference calendar (2026):
  Fri 17 Jul, Sat 18 Jul, Sun 19 Jul, Mon 20 Jul, Tue 21 Jul
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.sync.catchup import last_expected_trading_day

JAKARTA = ZoneInfo("Asia/Jakarta")


def _wib(y: int, m: int, d: int, hour: int) -> datetime:
    return datetime(y, m, d, hour, tzinfo=JAKARTA)


def test_weekday_evening_expects_today():
    # Tuesday 19:00, after the close has been published
    assert last_expected_trading_day(_wib(2026, 7, 21, 19)) == date(2026, 7, 21)


def test_weekday_morning_expects_previous_weekday():
    # Tuesday 09:00 — today's bar does not exist yet, so Monday is the latest
    assert last_expected_trading_day(_wib(2026, 7, 21, 9)) == date(2026, 7, 20)


def test_monday_morning_steps_back_over_the_weekend():
    # Monday 08:00 -> Sunday -> Saturday -> Friday
    assert last_expected_trading_day(_wib(2026, 7, 20, 8)) == date(2026, 7, 17)


def test_weekend_expects_friday():
    assert last_expected_trading_day(_wib(2026, 7, 18, 20)) == date(2026, 7, 17)
    assert last_expected_trading_day(_wib(2026, 7, 19, 11)) == date(2026, 7, 17)


def test_friday_evening_expects_friday():
    assert last_expected_trading_day(_wib(2026, 7, 17, 18)) == date(2026, 7, 17)


def test_exactly_at_the_publish_hour_counts_as_published():
    # 18:00 is the boundary: the bar is considered available
    assert last_expected_trading_day(_wib(2026, 7, 21, 18)) == date(2026, 7, 21)
    assert last_expected_trading_day(_wib(2026, 7, 21, 17)) == date(2026, 7, 20)


# --------------------------------------------------------------------------
# Never store an unfinished session
# --------------------------------------------------------------------------

import pandas as pd

from app.sync.prices import _df_to_rows, _last_final_trade_date


def _frame(days: list[int], close: int = 100) -> pd.DataFrame:
    idx = pd.to_datetime([f"2026-07-{d:02d}" for d in days])
    return pd.DataFrame(
        {
            "Open": [close] * len(days),
            "High": [close] * len(days),
            "Low": [close] * len(days),
            "Close": [close] * len(days),
            "Volume": [1000] * len(days),
        },
        index=idx,
    )


def test_current_session_is_not_stored_before_the_bar_is_published():
    """Yahoo returns the in-progress day as an ordinary row. Storing it makes
    a live price look like a settled close — the KETR case, where a bar was
    written mid-session at 565 and kept it while the real close was 615."""
    # Tuesday 21 Jul, 11:00 WIB — the session is still open
    rows = _df_to_rows(_frame([20, 21]), now=_wib(2026, 7, 21, 11))
    assert [r["trade_date"] for r in rows] == [date(2026, 7, 20)]


def test_current_session_is_stored_once_published():
    # same day at 19:00 WIB — the close is final
    rows = _df_to_rows(_frame([20, 21]), now=_wib(2026, 7, 21, 19))
    assert [r["trade_date"] for r in rows] == [date(2026, 7, 20), date(2026, 7, 21)]


def test_completed_days_are_always_stored():
    rows = _df_to_rows(_frame([17, 20]), now=_wib(2026, 7, 21, 11))
    assert [r["trade_date"] for r in rows] == [date(2026, 7, 17), date(2026, 7, 20)]


def test_writer_will_always_store_the_day_the_catch_up_demands():
    """The two halves of the bug: `prices` decides what may be WRITTEN and
    `catchup` decides what should EXIST.

    The invariant is `cutoff >= expected`, not equality — the two are allowed
    to differ over a weekend, where the catch-up steps back to Friday while
    the cutoff simply says "not today". That is harmless because no bar exists
    on a Saturday.

    What must never happen is the reverse: a cutoff earlier than the expected
    day would mean the catch-up keeps demanding a bar the writer refuses to
    store, re-running the daily sync on every startup and never settling.
    """
    for day in range(17, 27):  # Fri 17 Jul .. Sun 26 Jul 2026, spans two weekends
        for hour in (0, 9, 11, 17, 18, 19, 23):
            now = _wib(2026, 7, day, hour)
            assert _last_final_trade_date(now) >= last_expected_trading_day(now), (
                f"cutoff {_last_final_trade_date(now)} is behind expected "
                f"{last_expected_trading_day(now)} at {now}"
            )


def test_cutoff_never_includes_an_open_session():
    """Whatever the weekday, the current day is only storable after the bar
    is published — that is the whole point of the guard."""
    for day in range(17, 27):
        for hour in range(0, 18):
            now = _wib(2026, 7, day, hour)
            assert _last_final_trade_date(now) < now.date()
        for hour in (18, 20, 23):
            now = _wib(2026, 7, day, hour)
            assert _last_final_trade_date(now) == now.date()


# --------------------------------------------------------------------------
# Never store a bar for a day the exchange was shut
#
# Real case: 27-28 May 2026 (Idul Adha + cuti bersama). Yahoo omits IDX
# holidays from ^JKSE but synthesises them for individual tickers, copying
# the previous close into O/H/L/C with volume 0. 191 such rows reached
# price_history across eight 2026 holidays, and each drew a bodiless candle
# on a day nothing traded. The five-year backfill never had the problem:
# long-range Yahoo requests omit holidays, so this is a nightly-path bug.
# --------------------------------------------------------------------------

from app.sync.prices import session_dates


def _holiday_frame(days: list[int], close: int = 100) -> pd.DataFrame:
    """A ticker frame where every bar is Yahoo's holiday placeholder."""
    idx = pd.to_datetime([f"2026-07-{d:02d}" for d in days])
    return pd.DataFrame(
        {
            "Open": [close] * len(days),
            "High": [close] * len(days),
            "Low": [close] * len(days),
            "Close": [close] * len(days),
            "Volume": [0] * len(days),
        },
        index=idx,
    )


def test_holiday_placeholder_is_not_stored():
    # the index traded on the 20th and the 22nd; the 21st was a holiday
    sessions = session_dates(_frame([20, 22]))
    rows = _df_to_rows(
        _frame([20, 21, 22]), now=_wib(2026, 7, 23, 19), sessions=sessions
    )
    assert [r["trade_date"] for r in rows] == [date(2026, 7, 20), date(2026, 7, 22)]


def test_untraded_stock_on_a_real_session_is_still_stored():
    """The discriminator that matters. An illiquid stock with no trades
    produces a bar identical in shape to a holiday placeholder — flat OHLC,
    zero volume — but the exchange WAS open, so the bar is real. 892 days of
    stored history look like this and none may be dropped."""
    sessions = session_dates(_frame([20, 21, 22]))
    rows = _df_to_rows(
        _holiday_frame([20, 21, 22]), now=_wib(2026, 7, 23, 19), sessions=sessions
    )
    assert [r["trade_date"] for r in rows] == [
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
    ]


def test_missing_calendar_fails_open():
    """A failed index fetch must not block every ticker's bars for the night.
    The cost is one holiday bar slipping through, which is the old behaviour."""
    assert session_dates(pd.DataFrame()) is None
    rows = _df_to_rows(_frame([20, 21]), now=_wib(2026, 7, 21, 19), sessions=None)
    assert [r["trade_date"] for r in rows] == [date(2026, 7, 20), date(2026, 7, 21)]


# --------------------------------------------------------------------------
# The read-path twin: never SERVE a holiday bar either
#
# The write guard above stops new ones. This one covers rows already stored
# before it existed (79 in production, 191 locally) and anything the
# write guard's fail-open path lets through on a night the benchmark fetch
# dies. Pure, so it needs no fixtures and cannot contaminate the shared
# BBCA/IHSG series the endpoint tests assert exact point counts against.
# --------------------------------------------------------------------------

from dataclasses import dataclass

from app.sync.prices import drop_holiday_placeholders


@dataclass
class _Bar:
    trade_date: date
    open: int
    high: int
    low: int
    close: int
    volume: int


def _bar(day: int, *, traded: bool = True) -> _Bar:
    d = date(2026, 7, day)
    if traded:
        return _Bar(d, 100, 110, 90, 105, 1_000_000)
    return _Bar(d, 100, 100, 100, 100, 0)  # flat, no volume


def _days(bars) -> list[int]:
    return [b.trade_date.day for b in bars]


def test_holiday_bar_is_not_served():
    # index printed on the 20th and 22nd; the 21st was a holiday
    index = {date(2026, 7, 20), date(2026, 7, 22)}
    bars = [_bar(20), _bar(21, traded=False), _bar(22)]
    assert _days(drop_holiday_placeholders(bars, index)) == [20, 22]


def test_untraded_stock_on_a_real_session_is_still_served():
    """The discriminator. Identical shape to a holiday bar — flat OHLC, zero
    volume — but the index printed, so the exchange was open and the bar is
    real. Hundreds of stored days look like this and none may be dropped."""
    index = {date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 22)}
    bars = [_bar(20), _bar(21, traded=False), _bar(22)]
    assert _days(drop_holiday_placeholders(bars, index)) == [20, 21, 22]


def test_a_traded_bar_is_never_dropped_even_without_an_index_close():
    """Shape alone must not condemn a bar: if it carries volume it is real,
    whatever the index did."""
    index = {date(2026, 7, 20), date(2026, 7, 22)}
    bars = [_bar(20), _bar(21), _bar(22)]  # the 21st TRADED
    assert _days(drop_holiday_placeholders(bars, index)) == [20, 21, 22]


def test_bars_outside_the_index_range_are_kept():
    """A stock whose history starts before the benchmark's, or runs past it,
    must not be truncated — outside that span there is nothing to compare."""
    index = {date(2026, 7, 21)}
    bars = [_bar(20, traded=False), _bar(21), _bar(22, traded=False)]
    assert _days(drop_holiday_placeholders(bars, index)) == [20, 21, 22]


def test_no_index_at_all_keeps_everything():
    """Without a benchmark there is no way to tell a holiday from a quiet
    day, and guessing would silently delete real history."""
    bars = [_bar(20), _bar(21, traded=False)]
    assert _days(drop_holiday_placeholders(bars, set())) == [20, 21]
