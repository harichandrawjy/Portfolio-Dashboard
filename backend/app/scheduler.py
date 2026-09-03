import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger

from app.demo import purge_expired_demo_users
from app.mail import Message, send as send_mail
from app.sync.fundamentals import sync_fundamentals
from app.sync.prices import backfill_ticker, sync_daily, sync_quotes

JAKARTA = ZoneInfo("Asia/Jakarta")

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    scheduler = AsyncIOScheduler(timezone=JAKARTA)

    # There is deliberately NO universe job here.
    #
    # It used to run nightly at 21:00, crawling IDX's JSON endpoints for the
    # day's listing changes. IDX's terms permit non-commercial use of their
    # data but exclude obtaining it by "web scrapping/crawling", and a job on
    # a timer is squarely that. The universe now comes from the snapshot
    # committed at data/idx_universe.csv, refreshed by hand with
    # `python -m app.sync universe --from-idx` from a machine where IDX
    # answers. See app/sync/universe.py.
    #
    # Nothing was lost operationally: Cloudflare 403s datacenter IPs, so the
    # scheduled crawl had failed on every single run since this deployed and
    # fallen through to that same snapshot anyway.
    #
    # Yahoo (bars, quotes, fundamentals, statements) is a separate question
    # and those jobs stay — see DEPLOY.md.

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


def enqueue_quote_refresh(ticker: str) -> None:
    """One-shot refresh of a single ticker's `latest_quotes` row, used by the
    API right after a transaction changes what a portfolio holds.

    The scheduled `sync_quotes` only looks at tickers someone currently
    holds (see its docstring), so a ticker that drops out of `holdings` and
    back in within one 15-minute window — a sell that gets edited or
    deleted, say — sits on a quote frozen from before it left, until the
    next tick happens to notice it is held again. That produced exactly the
    bug this closes: cancelling a sell left the ticker's price and its
    provisional candle reading yesterday's close for up to 15 minutes after
    the position was back.

    A distinct job id from the periodic "quote-refresh" job, so triggering
    this never touches that one's schedule; keyed by ticker so repeated
    triggers for the same ticker replace each other instead of queuing up.
    """
    if _scheduler is None or not _scheduler.running:
        raise RuntimeError("scheduler is not running")
    _scheduler.add_job(
        sync_quotes,
        args=[[ticker]],
        id=f"quote-refresh-now-{ticker}",
        replace_existing=True,
        misfire_grace_time=None,
    )


async def _deliver(message: Message) -> None:
    """Send one message, swallowing failure.

    Deliberately does not re-raise. An unreachable Gmail must not surface as a
    500 on a registration that already succeeded — the account row is
    committed by the time this runs, and the user's recourse is the resend
    button, not a retry of the signup they cannot repeat. The exception is
    logged with the recipient so a delivery problem is diagnosable.
    """
    try:
        await asyncio.to_thread(send_mail, message)
    except Exception:
        logger.exception("could not deliver %r to %s", message.subject, message.to)


def enqueue_email(message: Message) -> None:
    """Hand a message to the scheduler and return immediately.

    Two reasons this is not simply awaited in the handler. Architecture
    decision 4 keeps external calls out of request handlers; and a handler
    that waits on SMTP times its own response, which turns
    `/auth/password/forgot` into an oracle — a fast 200 for an unknown
    address, a slow one for a real account. Enqueuing makes both identical.

    No job id, so nothing dedupes: two verification emails are a minor
    annoyance, one silently dropped because it collided with another is a
    person who cannot sign in.
    """
    if _scheduler is None or not _scheduler.running:
        # Only tests and CLI paths get here — the app's lifespan starts the
        # scheduler before it serves anything. Deliver inline rather than drop
        # it: losing every verification email is a far worse failure than
        # blocking a caller that, in these contexts, is not a real request.
        # With SMTP unconfigured (which is when this path is reached) `send`
        # only appends to OUTBOX, so nothing actually blocks.
        logger.warning("no scheduler — delivering %r inline", message.subject)
        try:
            send_mail(message)
        except Exception:
            logger.exception("inline delivery of %r failed", message.subject)
        return
    _scheduler.add_job(_deliver, args=[message], misfire_grace_time=None)
