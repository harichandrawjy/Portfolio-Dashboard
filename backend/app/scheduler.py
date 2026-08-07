from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger

from app.demo import purge_expired_demo_users
from app.sync.fundamentals import sync_fundamentals
from app.sync.prices import backfill_ticker, sync_daily, sync_quotes
from app.sync.universe import sync_universe

JAKARTA = ZoneInfo("Asia/Jakarta")

_scheduler: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    scheduler = AsyncIOScheduler(timezone=JAKARTA)

    # Nightly, hours after the 16:00 WIB close so the day's listing changes
    # are published on IDX's side.
    scheduler.add_job(
        sync_universe,
        CronTrigger(hour=21, minute=0, timezone=JAKARTA),
        id="universe-sync",
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Daily bars appear on Yahoo shortly after close; 18:30 leaves margin.
    scheduler.add_job(
        sync_daily,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30, timezone=JAKARTA),
        id="daily-prices",
        coalesce=True,
        misfire_grace_time=3600,
    )

    # Delayed quotes every 15 min during IDX trading hours (09:00–16:00 WIB).
    scheduler.add_job(
        sync_quotes,
        OrTrigger(
            [
                CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/15", timezone=JAKARTA),
                CronTrigger(day_of_week="mon-fri", hour=16, minute=0, timezone=JAKARTA),
            ]
        ),
        id="quote-refresh",
        coalesce=True,
        misfire_grace_time=300,
    )

    # Fundamentals barely change; Saturday morning after the week closes.
    scheduler.add_job(
        sync_fundamentals,
        CronTrigger(day_of_week="sat", hour=6, minute=0, timezone=JAKARTA),
        id="fundamentals-sync",
        coalesce=True,
        misfire_grace_time=6 * 3600,
    )

    # Financial statements right after — same weekly cadence.
    from app.sync.statements import sync_statements

    scheduler.add_job(
        sync_statements,
        CronTrigger(day_of_week="sat", hour=6, minute=30, timezone=JAKARTA),
        id="statements-sync",
        coalesce=True,
        misfire_grace_time=6 * 3600,
    )

    # Every visitor who clicks "explore the demo" leaves a user row behind.
    # They are disposable by construction (app/demo.py), but nothing else
    # deletes them, so without this the table grows for the lifetime of the
    # deployment. 04:00 is after the day's syncs and before anyone is awake.
    scheduler.add_job(
        purge_expired_demo_users,
        CronTrigger(hour=4, minute=0, timezone=JAKARTA),
        id="demo-purge",
        coalesce=True,
        misfire_grace_time=6 * 3600,
    )

    _scheduler = scheduler
    return scheduler


def enqueue_backfill(ticker: str) -> None:
    """One-shot 5y backfill, used by the API the first time a ticker is
    added to a portfolio or opened on the stock detail page.

    The job id dedupes concurrent requests for the same ticker; the job
    runs immediately on the scheduler's event loop, off the request path.
    """
    if _scheduler is None or not _scheduler.running:
        raise RuntimeError("scheduler is not running")
    _scheduler.add_job(
        backfill_ticker,
        args=[ticker],
        id=f"backfill-{ticker}",
        replace_existing=True,
        misfire_grace_time=None,
    )
