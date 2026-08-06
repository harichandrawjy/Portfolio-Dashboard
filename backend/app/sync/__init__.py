"""Shared constants for the sync jobs.

Deliberately dependency-free: `catchup` imports from here at module scope and
must not drag pandas/yfinance into every app startup, which is why this does
not live in `prices`.
"""

# IDX closes 16:00 WIB, and Yahoo finalises the daily bar somewhat after. A
# bar for a given weekday is only trustworthy once this hour has arrived.
#
# Two places depend on it and must agree:
#   * `prices._df_to_rows` refuses to STORE a bar before it, so an in-progress
#     session is never persisted as a finished candle;
#   * `catchup.last_expected_trading_day` uses it to decide which day's bar
#     should already exist.
#
# Keeping one value is what stops the two from disagreeing: yfinance returns
# the current day's in-progress bar, so a sync during market hours used to
# write a partial candle, and the catch-up then saw *a* bar for that date and
# concluded nothing was missing — leaving a mid-session snapshot frozen on the
# chart as if it were the close.
BAR_PUBLISHED_HOUR_WIB = 18
