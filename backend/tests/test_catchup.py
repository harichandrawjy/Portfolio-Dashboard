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
