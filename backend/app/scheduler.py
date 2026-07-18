from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.sync.universe import sync_universe

JAKARTA = ZoneInfo("Asia/Jakarta")


def create_scheduler() -> AsyncIOScheduler:
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
    return scheduler
