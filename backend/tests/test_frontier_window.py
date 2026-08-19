"""The frontier's estimation window: the last COMPLETE calendar year.

Worth its own tests because the rule is a date rule with one hard edge — the
turn of the year — and getting it wrong is silent. A window that quietly
included the current year would grow a session a day and change the answer
overnight for no visible reason, which is the exact failure a fixed window
exists to prevent.
"""

from datetime import date

import pytest

from app.routers.performance import frontier_window


@pytest.mark.parametrize(
    ("today", "year"),
    [
        (date(2026, 8, 19), 2025),   # mid-year
        (date(2026, 1, 1), 2025),    # first instant of a year
        (date(2026, 12, 31), 2025),  # last instant — still the year before
        (date(2027, 1, 1), 2026),    # the rollover, to the day
        (date(2027, 6, 15), 2026),
    ],
)
def test_window_is_the_last_complete_year(today: date, year: int) -> None:
    start, end, got = frontier_window(today)
    assert got == year
    assert start == date(year, 1, 1)
    assert end == date(year, 12, 31)


def test_window_never_includes_today() -> None:
    """The current year is excluded however far into it we are.

    This is the property that makes the estimate quotable: two people asking
    on different days of the same year get identical numbers.
    """
    for day in (date(2026, 1, 1), date(2026, 7, 1), date(2026, 12, 31)):
        _, end, _ = frontier_window(day)
        assert end < date(day.year, 1, 1)


def test_window_is_stable_across_a_whole_year() -> None:
    windows = {frontier_window(date(2026, m, 1)) for m in range(1, 13)}
    assert len(windows) == 1, "window must not move within a calendar year"


def test_leap_year_end_is_december_31() -> None:
    start, end, year = frontier_window(date(2025, 3, 1))
    assert (start, end, year) == (date(2024, 1, 1), date(2024, 12, 31), 2024)
