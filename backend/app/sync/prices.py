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
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy import func, or_, select, update
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import LatestQuote, PriceHistory, Security
from app.sync.universe import BENCHMARK

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


def _download_quote(symbol: str) -> tuple[int, Decimal | None, datetime]:
    """Return (price, change_pct vs previous close, provider 'as of' time)."""
    ticker = yf.Ticker(symbol)
    hist = _retryable_quote_history(ticker, symbol)
    price = float(hist["Close"].iloc[-1])

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
    return round(price), change_pct, as_of


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


def _df_to_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for idx, r in df.iterrows():
        close = r.get("Close")
        if close is None or pd.isna(close):
            continue  # gap day for an illiquid small cap — store nothing
        volume = r.get("Volume")
        rows.append(
            {
                "trade_date": idx.date(),
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
    rows = _df_to_rows(df)
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

    for sec in secs:
        try:
            df = await asyncio.to_thread(_download_history, sec.yahoo_symbol, "5d")
            rows = _df_to_rows(df)
            if not rows:
                logger.warning(
                    "no recent bars for %s (%s) — suspended or stale on Yahoo",
                    sec.ticker, sec.yahoo_symbol,
                )
                result.failed.append(sec.ticker)
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
            price, change_pct, as_of = await asyncio.to_thread(
                _download_quote, sec.yahoo_symbol
            )
            async with SessionLocal() as session:
                async with session.begin():
                    stmt = pg_insert(LatestQuote).values(
                        security_id=sec.id,
                        price=price,
                        change_pct=change_pct,
                        as_of=as_of,
                        fetched_at=func.now(),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["security_id"],
                        set_={
                            "price": stmt.excluded.price,
                            "change_pct": stmt.excluded.change_pct,
                            "as_of": stmt.excluded.as_of,
                            "fetched_at": stmt.excluded.fetched_at,
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
