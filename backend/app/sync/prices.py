"""yfinance price sync — on-demand backfill, nightly increments, quote refresh.

The IDX sync answers "what exists"; Yahoo answers "what is it worth".
Policies:
  - No blanket backfill. A ticker gets 5 years of daily OHLCV the first
    time a portfolio (or the stock detail page) needs it, via idempotent
    upserts keyed on (security_id, trade_date).
  - Nightly increments cover only tickers that already have history,
    plus ^JKSE always — we never store data nobody asked for.
  - A ticker is only "activated" for nightly sync by having rows in
    price_history, and rows only appear once its yahoo_symbol actually
    resolves — the resolve check and the activation gate are the same thing.
  - Every Yahoo call retries with backoff, and every ticker is isolated:
    one bad symbol must never kill a run.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy import func, or_, select, update
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import LatestQuote, PriceHistory, Security
from app.sync import BAR_PUBLISHED_HOUR_WIB
from app.sync.universe import BENCHMARK

JAKARTA = ZoneInfo("Asia/Jakarta")

logger = logging.getLogger(__name__)

REQUEST_PAUSE = 0.6  # polite gap between consecutive Yahoo calls
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0
UPSERT_CHUNK = 500


class YahooError(Exception):
    """A Yahoo request kept failing after retries."""


class UnknownTickerError(Exception):
    """Ticker is not in the securities table (universe sync hasn't seen it)."""


@dataclass
class BackfillResult:
    ticker: str
    symbol: str
    rows: int
    resolved: bool


@dataclass
class SyncRunResult:
    synced: int = 0
    failed: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Yahoo calls (synchronous; always invoked via asyncio.to_thread)
# --------------------------------------------------------------------------

def _download_history(symbol: str, period: str) -> pd.DataFrame:
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return yf.Ticker(symbol).history(
                period=period, interval="1d", auto_adjust=False
            )
        except Exception as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)
                logger.warning(
                    "Yahoo history %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    symbol, attempt, RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
    raise YahooError(f"history fetch for {symbol} failed after {RETRY_ATTEMPTS} attempts") from last_exc


@dataclass(slots=True)
class QuoteSnapshot:
    """The latest price plus the session's bar so far.

    The OHLC is carried because the download already contains it — the frame
    below IS today's bar — and the chart needs a provisional candle for a
    session that `price_history` will not accept until it closes. It is
    display-only: nothing derived reads it.
    """

    price: int
    change_pct: Decimal | None
    as_of: datetime
    trade_date: date | None
    open: int | None
    high: int | None
    low: int | None
    volume: int | None


def _download_quote(symbol: str) -> QuoteSnapshot:
    """Return the latest price and the in-progress bar behind it."""
    ticker = yf.Ticker(symbol)
    hist = _retryable_quote_history(ticker, symbol)
    price = float(hist["Close"].iloc[-1])
    bar = hist.iloc[-1]
    bar_date = hist.index[-1].date()

    meta = ticker.history_metadata or {}
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change_pct = None
    if prev:
        change_pct = Decimal(f"{(price - float(prev)) / float(prev) * 100:.4f}")

    market_time = meta.get("regularMarketTime")
    if isinstance(market_time, (int, float)):
        as_of = datetime.fromtimestamp(market_time, tz=timezone.utc)
    else:
        as_of = datetime.now(tz=timezone.utc)

    def _px(field: str) -> int | None:
        v = bar.get(field)
        return None if v is None or pd.isna(v) else _to_idr(v)

    vol = bar.get("Volume")
    return QuoteSnapshot(
        price=round(price),
        change_pct=change_pct,
        as_of=as_of,
        trade_date=bar_date,
        open=_px("Open"),
        high=_px("High"),
        low=_px("Low"),
        volume=None if vol is None or pd.isna(vol) else int(vol),
    )


def _retryable_quote_history(ticker: yf.Ticker, symbol: str) -> pd.DataFrame:
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            hist = ticker.history(period="1d", interval="1d", auto_adjust=False)
            if hist.empty:
                raise YahooError(f"no quote data for {symbol}")
            return hist
        except Exception as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)
                logger.warning(
                    "Yahoo quote %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    symbol, attempt, RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
    raise YahooError(f"quote fetch for {symbol} failed after {RETRY_ATTEMPTS} attempts") from last_exc


def _to_idr(value) -> int | None:
    """IDX trades in whole rupiah; ^JKSE index points round the same way."""
    if value is None or pd.isna(value):
        return None
    return round(float(value))


# IDX auto-rejection caps a single session's move at roughly 20-35%, so an
# overnight close-to-close ratio outside this band cannot be a real price
# move. Kept deliberately wide (a ~2:1 action or larger) so ordinary
# volatility is never mistaken for a corporate action; smaller unflagged
# actions are left alone rather than risk corrupting good data.
SPLIT_RATIO_UP = 1.8
SPLIT_RATIO_DOWN = 0.55


def adjust_corporate_actions(rows: list[dict]) -> list[dict]:
    """Back-adjust prices across corporate actions Yahoo did not flag.

    Yahoo carries no split/rights record for some IDX issuers (PACK, for
    one), leaving a raw discontinuity — pre-action prices sitting an order
    of magnitude above post-action ones, which renders as a cliff on the
    chart and a fictitious loss in any return computed across it.

    Bars before each detected action are rescaled onto the current basis,
    exactly what an adjustment factor would do; volume moves inversely,
    since a split multiplies share count. `rows` is oldest first.
    """
    if len(rows) < 2:
        return rows

    factors = [1.0] * len(rows)
    cumulative = 1.0
    for i in range(len(rows) - 1, 0, -1):
        prev_close = rows[i - 1]["close"]
        close = rows[i]["close"]
        if prev_close and close:
            ratio = close / prev_close
            if ratio >= SPLIT_RATIO_UP or ratio <= SPLIT_RATIO_DOWN:
                cumulative *= ratio
                logger.info(
                    "corporate action detected on %s: close %s -> %s "
                    "(x%.4f); back-adjusting earlier bars",
                    rows[i]["trade_date"], prev_close, close, ratio,
                )
        factors[i - 1] = cumulative

    if cumulative == 1.0:
        return rows

    adjusted = []
    for row, factor in zip(rows, factors):
        if factor == 1.0:
            adjusted.append(row)
            continue
        out = dict(row)
        for field in ("open", "high", "low", "close"):
            if out[field] is not None:
                out[field] = max(1, round(out[field] * factor))
        if out["volume"] is not None and factor:
            out["volume"] = round(out["volume"] / factor)
        adjusted.append(out)
    return adjusted


def _last_final_trade_date(now: datetime | None = None) -> date:
    """The newest date whose bar may be stored.

    Yahoo returns the CURRENT session as an ordinary row, with `Close` holding
    the last trade so far. Storing it makes a live price look like a settled
    close, and nothing later guarantees a correction: the 18:30 job only runs
    if the machine happens to be awake, and the startup catch-up compares
    dates, so a partial bar for today makes it conclude today is already done.

    Real case: KETR's 2026-08-04 bar was written mid-session at 565 and kept
    that value, while the true close was 615 — the chart showed a candle the
    market never printed.
    """
    wib = (now or datetime.now(tz=JAKARTA)).astimezone(JAKARTA)
    if wib.hour >= BAR_PUBLISHED_HOUR_WIB:
        return wib.date()
    return wib.date() - timedelta(days=1)


def session_dates(df: pd.DataFrame) -> set[date] | None:
    """The dates the exchange actually traded, read off the benchmark index.

    `None` means "unusable — do not filter". A failed or empty index fetch
    must never block every ticker's bars; the cost of that failure mode is
    one holiday bar slipping through, which is what we had before.
    """
    if df is None or df.empty or "Close" not in df:
        return None
    return {idx.date() for idx, r in df.iterrows() if not pd.isna(r.get("Close"))}


def drop_holiday_placeholders(bars, index_dates) -> list:
    """Remove bars for days the exchange was shut.

    The read-path twin of the `sessions` filter in `_df_to_rows`. That one
    stops holiday placeholders being WRITTEN; this one stops any already
    stored from being SERVED — rows that predate the write guard, or that
    its fail-open path let through on a night the benchmark fetch died.

    `bars` is any sequence of objects carrying trade_date/open/high/low/
    close/volume. `index_dates` is the set of dates the benchmark printed.

    BOTH conditions are required to drop a bar, and neither is sufficient:

      - a missing index close only means the benchmark did not print, which
        is also true outside the range the benchmark covers at all;
      - the placeholder SHAPE only means nothing traded, which is equally
        true of an illiquid stock on a day the exchange WAS open. Hundreds
        of days of stored history look exactly like that and every one of
        them is real.

    Together they are specific: the market was open (the index brackets this
    date) but printed nothing on it, and this bar carries no trade.

    An empty `index_dates` returns the bars untouched — without a benchmark
    there is no way to tell a holiday from a quiet day, and guessing would
    silently delete real history.
    """
    if not index_dates:
        return list(bars)
    lo, hi = min(index_dates), max(index_dates)

    def shut(bar) -> bool:
        d = bar.trade_date
        if not lo <= d <= hi or d in index_dates:
            return False
        return bar.volume == 0 and bar.open == bar.high == bar.low == bar.close

    return [bar for bar in bars if not shut(bar)]


def _df_to_rows(
    df: pd.DataFrame,
    now: datetime | None = None,
    sessions: set[date] | None = None,
) -> list[dict]:
    cutoff = _last_final_trade_date(now)
    rows = []
    for idx, r in df.iterrows():
        trade_date = idx.date()
        if trade_date > cutoff:
            # the session is still open (or too fresh to trust) — skip it and
            # let the evening run store the real bar
            continue
        if sessions is not None and trade_date not in sessions:
            # An IDX holiday. Yahoo does not omit these for individual
            # tickers the way it does for ^JKSE — it synthesises a bar with
            # the previous close copied into O/H/L/C and volume 0, which
            # renders as a bodiless candle on a day the exchange was shut.
            # The guard below cannot catch it, because that close is a real
            # number rather than NaN.
            #
            # The index is the authority on whether the market opened: if
            # ^JKSE printed nothing, nothing traded. That distinguishes a
            # closed market from a single illiquid stock that simply had no
            # trades, which produces an identical-looking bar on a day the
            # exchange really was open — 892 such days are in the history and
            # none of them should be touched.
            continue
        close = r.get("Close")
        if close is None or pd.isna(close):
            continue  # gap day for an illiquid small cap — store nothing
        volume = r.get("Volume")
        rows.append(
            {
                "trade_date": trade_date,
                "open": _to_idr(r.get("Open")),
                "high": _to_idr(r.get("High")),
                "low": _to_idr(r.get("Low")),
                "close": _to_idr(close),
                "volume": None if volume is None or pd.isna(volume) else int(volume),
            }
        )
    return rows


# --------------------------------------------------------------------------
# Database plumbing
# --------------------------------------------------------------------------

async def _resolve_security(ident: str) -> Security | None:
    """Accept either an IDX code ('BBCA') or a yahoo symbol ('^JKSE')."""
    ident = ident.strip().upper()
    async with SessionLocal() as session:
        return await session.scalar(
            select(Security).where(
                or_(Security.ticker == ident, Security.yahoo_symbol == ident)
            )
        )


async def _upsert_history(security_id, rows: list[dict]) -> None:
    # Yahoo occasionally repeats an index date; last one wins so a single
    # INSERT never touches the same row twice.
    deduped = list({r["trade_date"]: r for r in rows}.values())
    payload = [{"security_id": security_id, **r} for r in deduped]

    async with SessionLocal() as session:
        async with session.begin():
            for start in range(0, len(payload), UPSERT_CHUNK):
                chunk = payload[start : start + UPSERT_CHUNK]
                stmt = pg_insert(PriceHistory).values(chunk)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["security_id", "trade_date"],
                    set_={
                        c: stmt.excluded[c]
                        for c in ("open", "high", "low", "close", "volume")
                    },
                )
                await session.execute(stmt)
            await session.execute(
                update(Security)
                .where(Security.id == security_id)
                .values(last_synced_at=func.now())
            )


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

async def backfill_ticker(ticker: str, years: int = 5) -> BackfillResult:
    """Idempotent 5-year daily OHLCV backfill for one ticker."""
    sec = await _resolve_security(ticker)
    if sec is None:
        raise UnknownTickerError(
            f"{ticker!r} is not in the securities table — run universe sync first"
        )

    df = await asyncio.to_thread(_download_history, sec.yahoo_symbol, f"{years}y")
    # Full-history fetch is the only place the whole series is in hand, so
    # it is where unflagged corporate actions can be back-adjusted.
    rows = adjust_corporate_actions(_df_to_rows(df))
    if not rows:
        logger.error(
            "%s (%s) returned no usable history from Yahoo — NOT activated for price sync",
            sec.ticker, sec.yahoo_symbol,
        )
        return BackfillResult(sec.ticker, sec.yahoo_symbol, 0, resolved=False)

    await _upsert_history(sec.id, rows)
    logger.info(
        "backfilled %s (%s): %d daily bars upserted", sec.ticker, sec.yahoo_symbol, len(rows)
    )
    # Fresh history means the stat cache for this ticker is computable now —
    # do it here so the stock page has stats seconds after first visit.
    from app.sync.stats import refresh_stats

    await refresh_stats([sec.id])

    # Fundamentals and statements too, so a first visit shows a complete
    # page; failures are non-fatal (the weekly Saturday jobs retry).
    try:
        from app.sync.fundamentals import sync_fundamentals

        await sync_fundamentals([sec.ticker])
    except Exception:
        logger.warning(
            "first-use fundamentals fetch failed for %s — weekly job will retry",
            sec.ticker,
        )
    try:
        from app.sync.statements import sync_statements

        await sync_statements([sec.ticker])
    except Exception:
        logger.warning(
            "first-use statements fetch failed for %s — weekly job will retry",
            sec.ticker,
        )

    # And a quote, or a first visit has no live price and no candle for today.
    #
    # The scheduled quote job deliberately covers only HELD tickers plus the
    # benchmark — polling the whole 963-ticker universe every 15 minutes is not
    # viable. A ticker nobody holds therefore never gets a `latest_quotes` row
    # from it, and both the header price and the provisional bar are derived
    # from that row. Without this the symptom is oddly specific: today's candle
    # appears for stocks somebody owns and is missing for anything just looked
    # up. Non-fatal like the rest — stored history is still worth serving.
    try:
        await sync_quotes([sec.ticker])
    except Exception:
        logger.warning(
            "first-use quote fetch failed for %s — the page falls back to the "
            "last close until the next quote sync",
            sec.ticker,
        )
    return BackfillResult(sec.ticker, sec.yahoo_symbol, len(rows), resolved=True)


async def backfill_many(tickers: list[str], years: int = 5) -> list[BackfillResult]:
    results = []
    for i, ticker in enumerate(tickers):
        if i:
            await asyncio.sleep(REQUEST_PAUSE)
        try:
            results.append(await backfill_ticker(ticker, years))
        except Exception:
            logger.exception("backfill failed for %s — continuing with the rest", ticker)
            results.append(BackfillResult(ticker, "?", 0, resolved=False))
    return results


async def _needs_readjustment(security_id, rows: list[dict]) -> bool:
    """True when freshly fetched bars disagree with what is stored for the
    same dates — the signature of a corporate action applied upstream after
    our history was built."""
    async with SessionLocal() as session:
        for row in rows:
            stored = await session.scalar(
                select(PriceHistory.close).where(
                    PriceHistory.security_id == security_id,
                    PriceHistory.trade_date == row["trade_date"],
                )
            )
            if stored and row["close"]:
                ratio = row["close"] / stored
                if ratio >= SPLIT_RATIO_UP or ratio <= SPLIT_RATIO_DOWN:
                    return True
    return False


async def sync_daily() -> SyncRunResult:
    """Append recent daily bars for every ticker that already has history,
    plus ^JKSE always. A 5-day window self-heals short outages/holidays."""
    async with SessionLocal() as session:
        tracked_ids = set(
            (await session.execute(select(PriceHistory.security_id).distinct()))
            .scalars()
            .all()
        )
        secs = []
        if tracked_ids:
            secs = list(
                await session.scalars(
                    select(Security)
                    .where(Security.id.in_(tracked_ids))
                    .order_by(Security.ticker)
                )
            )
        bench = await session.scalar(
            select(Security).where(Security.yahoo_symbol == BENCHMARK["yahoo_symbol"])
        )

    result = SyncRunResult()

    if bench is None:
        logger.error("benchmark %s missing — run universe sync first", BENCHMARK["yahoo_symbol"])
    elif bench.id not in tracked_ids:
        # First run: the benchmark needs full history before increments make sense.
        try:
            res = await backfill_ticker(bench.yahoo_symbol)
            result.synced += 1 if res.resolved else 0
        except Exception:
            logger.exception("benchmark backfill failed — continuing")
            result.failed.append(bench.ticker)

    # The session calendar for this window, fetched before any ticker so the
    # filter is available to all of them. It must come from a live fetch
    # rather than from stored IHSG rows: `secs` is ordered by ticker, so
    # everything from AADI to GOTO is written before IHSG's own bar lands.
    sessions: set[date] | None = None
    if bench is not None:
        try:
            bench_df = await asyncio.to_thread(
                _download_history, bench.yahoo_symbol, "5d"
            )
            sessions = session_dates(bench_df)
        except Exception:
            logger.exception(
                "benchmark calendar fetch failed — storing bars unfiltered"
            )
        await asyncio.sleep(REQUEST_PAUSE)
    if sessions is None:
        logger.warning("no session calendar this run — holiday bars may slip through")

    for sec in secs:
        try:
            df = await asyncio.to_thread(_download_history, sec.yahoo_symbol, "5d")
            rows = _df_to_rows(df, sessions=sessions)
            if not rows:
                logger.warning(
                    "no recent bars for %s (%s) — suspended or stale on Yahoo",
                    sec.ticker, sec.yahoo_symbol,
                )
                result.failed.append(sec.ticker)
            elif await _needs_readjustment(sec.id, rows):
                # A corporate action landed since the last full fetch, so the
                # stored history is on the old basis. Re-backfill to rebuild
                # the whole series adjusted.
                logger.info(
                    "%s repriced against stored history — re-running the "
                    "full backfill to re-adjust",
                    sec.ticker,
                )
                # deliberately unfiltered: backfill_ticker fetches five
                # years, and `sessions` covers five days. Long-range Yahoo
                # requests omit holidays on their own, which is why every
                # phantom bar in the history is from this nightly path.
                await backfill_ticker(sec.ticker)
                result.synced += 1
            else:
                await _upsert_history(sec.id, rows)
                result.synced += 1
        except Exception:
            logger.exception("daily sync failed for %s — continuing", sec.ticker)
            result.failed.append(sec.ticker)
        await asyncio.sleep(REQUEST_PAUSE)

    logger.info(
        "daily price sync: %d synced, %d failed%s",
        result.synced, len(result.failed),
        f" ({', '.join(result.failed)})" if result.failed else "",
    )

    # New bars invalidate the nightly stat cache — rebuild it now.
    from app.sync.stats import refresh_stats

    await refresh_stats()
    return result


async def sync_quotes(tickers_override: list[str] | None = None) -> SyncRunResult:
    """Refresh latest_quotes for held tickers (holdings view) + ^JKSE.

    tickers_override exists for the CLI — manual refresh of an explicit list.
    """
    secs: list[Security] = []
    if tickers_override:
        for ident in tickers_override:
            sec = await _resolve_security(ident)
            if sec is None:
                logger.error("unknown ticker %r — skipping", ident)
            else:
                secs.append(sec)
    else:
        async with SessionLocal() as session:
            held_ids = (
                (await session.execute(sa_text("SELECT DISTINCT security_id FROM holdings")))
                .scalars()
                .all()
            )
            if held_ids:
                secs = list(
                    await session.scalars(
                        select(Security).where(Security.id.in_(held_ids))
                    )
                )

    bench = await _resolve_security(BENCHMARK["yahoo_symbol"])
    if bench is not None and bench.id not in {s.id for s in secs}:
        secs.append(bench)

    result = SyncRunResult()
    for i, sec in enumerate(secs):
        if i:
            await asyncio.sleep(REQUEST_PAUSE)
        try:
            snap = await asyncio.to_thread(_download_quote, sec.yahoo_symbol)
            async with SessionLocal() as session:
                async with session.begin():
                    stmt = pg_insert(LatestQuote).values(
                        security_id=sec.id,
                        price=snap.price,
                        change_pct=snap.change_pct,
                        as_of=snap.as_of,
                        fetched_at=func.now(),
                        trade_date=snap.trade_date,
                        open=snap.open,
                        high=snap.high,
                        low=snap.low,
                        volume=snap.volume,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["security_id"],
                        set_={
                            "price": stmt.excluded.price,
                            "change_pct": stmt.excluded.change_pct,
                            "as_of": stmt.excluded.as_of,
                            "fetched_at": stmt.excluded.fetched_at,
                            "trade_date": stmt.excluded.trade_date,
                            "open": stmt.excluded.open,
                            "high": stmt.excluded.high,
                            "low": stmt.excluded.low,
                            "volume": stmt.excluded.volume,
                        },
                    )
                    await session.execute(stmt)
            result.synced += 1
        except Exception:
            logger.exception("quote refresh failed for %s — continuing", sec.ticker)
            result.failed.append(sec.ticker)

    logger.info(
        "quote refresh: %d updated, %d failed%s",
        result.synced, len(result.failed),
        f" ({', '.join(result.failed)})" if result.failed else "",
    )
    return result
