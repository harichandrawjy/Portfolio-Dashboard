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
