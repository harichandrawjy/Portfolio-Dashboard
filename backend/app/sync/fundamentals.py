"""Weekly fundamentals sync from yfinance Ticker.info.

Fundamentals barely move week to week, so this runs Saturday mornings
(and via CLI). Only tickers that already have price history are fetched —
same lazy principle as prices: no data for stocks nobody looks at.

Yahoo's IDX coverage is patchy: large caps are generally complete, small
caps miss fields or carry stale ones. Every field is therefore nullable
and stored as-received (dividendYield arrives already in percent form in
current yfinance; verified against BBCA ~5.5%). A ticker with zero usable
fields still gets a row — last_updated then documents "we asked, Yahoo
had nothing", which the UI renders as an empty block with a timestamp.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from decimal import Decimal

import yfinance as yf
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Fundamentals, PriceHistory, Security
from app.sync.prices import REQUEST_PAUSE, RETRY_ATTEMPTS, RETRY_BASE_DELAY
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

FIELDS = ("marketCap", "trailingPE", "trailingEps", "dividendYield", "bookValue")


@dataclass
class FundamentalsResult:
    synced: int = 0
    failed: list[str] = field(default_factory=list)


def _fetch_info(symbol: str) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return yf.Ticker(symbol).info or {}
        except Exception as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)
                logger.warning(
                    "Yahoo info %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    symbol, attempt, RETRY_ATTEMPTS, exc, delay,
                )
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _num(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(f"{float(value):.4f}")
    except (ValueError, TypeError):
        return None


def _info_to_row(info: dict) -> dict:
    market_cap = info.get("marketCap")
    return {
        "market_cap": int(market_cap) if isinstance(market_cap, (int, float)) else None,
        "pe_ratio": _num(info.get("trailingPE")),
        "eps": _num(info.get("trailingEps")),
        "dividend_yield_pct": _num(info.get("dividendYield")),
        "book_value": _num(info.get("bookValue")),
    }


async def sync_fundamentals(tickers: list[str] | None = None) -> FundamentalsResult:
    """Refresh fundamentals for tracked tickers (or an explicit list)."""
    async with SessionLocal() as session:
        stmt = (
            select(Security)
            .join(PriceHistory, PriceHistory.security_id == Security.id)
            .where(Security.kind == "stock")
            .distinct()
            .order_by(Security.ticker)
        )
        if tickers is not None:
            stmt = stmt.where(Security.ticker.in_([t.strip().upper() for t in tickers]))
        secs = list(await session.scalars(stmt))

    result = FundamentalsResult()
    for i, sec in enumerate(secs):
        if i:
            await asyncio.sleep(REQUEST_PAUSE)
        try:
            info = await asyncio.to_thread(_fetch_info, sec.yahoo_symbol)
            row = _info_to_row(info)
            async with SessionLocal() as session:
                async with session.begin():
                    ins = pg_insert(Fundamentals).values(
                        security_id=sec.id, last_updated=func.now(), **row
                    )
                    ins = ins.on_conflict_do_update(
                        index_elements=["security_id"],
                        set_={"last_updated": func.now(), **row},
                    )
                    await session.execute(ins)
            missing = [k for k, v in row.items() if v is None]
            logger.info(
                "fundamentals %s: %s",
                sec.ticker,
                f"missing {', '.join(missing)}" if missing else "complete",
            )
            result.synced += 1
        except Exception:
            logger.exception("fundamentals failed for %s — continuing", sec.ticker)
            result.failed.append(sec.ticker)

    logger.info(
        "fundamentals sync: %d synced, %d failed%s",
        result.synced, len(result.failed),
        f" ({', '.join(result.failed)})" if result.failed else "",
    )
    return result
