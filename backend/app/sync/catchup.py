"""Startup catch-up: run the syncs that should have fired while we were down.

The scheduled jobs (daily bars 18:30 WIB, quotes every 15 min during market
hours) only fire while the backend is actually running. On a laptop that is
routinely asleep at 18:30 — and after a container crash — those windows are
simply missed; APScheduler does not replay them.

So on every startup we compare what is stored against what should exist by
now, and sync only what is behind. Both checks are cheap DB reads that
usually no-op, which matters because `--reload` restarts the app on every
file save during development.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import LatestQuote, PriceHistory
from app.sync import BAR_PUBLISHED_HOUR_WIB

logger = logging.getLogger(__name__)

JAKARTA = ZoneInfo("Asia/Jakarta")
# Don't re-hit Yahoo for quotes on every dev hot-reload.
QUOTE_STALE_AFTER = timedelta(minutes=30)
# Let the app start serving before hitting the network.
STARTUP_DELAY_SECONDS = 10


def last_expected_trading_day(now: datetime) -> date:
    """The most recent weekday whose daily bar should already be published.

    Weekends and pre-evening hours step back to the previous weekday. IDX
    holidays are not modelled: on a holiday the sync simply finds no new bar,
    which is a harmless no-op.
    """
    day = now.date()
    if day.weekday() >= 5 or now.hour < BAR_PUBLISHED_HOUR_WIB:
        day -= timedelta(days=1)
    while day.weekday() >= 5:  # Sat/Sun -> previous Friday
        day -= timedelta(days=1)
    return day


async def catch_up() -> None:
    """Sync anything that fell behind while the app was not running."""
    # Imported lazily: pulling yfinance in at module import would slow every
    # startup, including the ones where nothing is stale.
    from app.sync.prices import sync_daily, sync_quotes

    now = datetime.now(JAKARTA)
    expected = last_expected_trading_day(now)

    async with SessionLocal() as session:
        newest_bar = await session.scalar(select(func.max(PriceHistory.trade_date)))
        newest_quote = await session.scalar(select(func.max(LatestQuote.as_of)))

    if newest_bar is None:
        logger.info("catch-up: no price history stored yet — nothing to append")
    elif newest_bar < expected:
        logger.info(
            "catch-up: newest daily bar is %s but %s should be published — "
            "running the daily sync",
            newest_bar, expected,
        )
        await sync_daily()
    else:
        logger.info("catch-up: daily bars are current through %s", newest_bar)

    quote_age = (
        None
        if newest_quote is None
        else datetime.now(timezone.utc) - newest_quote
    )
    if quote_age is None or quote_age > QUOTE_STALE_AFTER:
        logger.info(
            "catch-up: quotes are %s — refreshing",
            "missing" if quote_age is None else f"{quote_age} old",
        )
        await sync_quotes()
    else:
        logger.info("catch-up: quotes are fresh (%s old)", quote_age)


async def run_catch_up_after_startup() -> None:
    """Background task started by the app lifespan. Never raises: a failed
    catch-up must not stop the API from serving stored data."""
    try:
        await asyncio.sleep(STARTUP_DELAY_SECONDS)
        await catch_up()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("startup catch-up failed — scheduled jobs will retry")
