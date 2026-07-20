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


def _f(value) -> float | None:
    """Plain float, or None for anything non-numeric (Yahoo loves gaps)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 4)
    except (ValueError, TypeError):
        return None


def _frac_pct(value) -> float | None:
    """Yahoo fraction (0.2543) -> percent (25.43)."""
    v = _f(value)
    return None if v is None else round(v * 100, 2)


def _i(value) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _epoch_date(value) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()


def _build_extra(info: dict) -> dict:
    """Whitelisted, normalized extended stats. Percent-form quirks are
    per-field (some Yahoo keys are fractions, some already percents) —
    verified against live payloads. Monetary income/balance figures are in
    financial_currency (IDX issuers report in IDR or USD)."""
    extra = {
        # valuation
        "enterprise_value": _i(info.get("enterpriseValue")),  # quote ccy (IDR)
        "forward_pe": _f(info.get("forwardPE")),
        "price_to_sales": _f(info.get("priceToSalesTrailing12Months")),
        "price_to_book": _f(info.get("priceToBook")),
        "ev_to_revenue": _f(info.get("enterpriseToRevenue")),
        "ev_to_ebitda": _f(info.get("enterpriseToEbitda")),
        # profitability (fractions -> %)
        "profit_margin_pct": _frac_pct(info.get("profitMargins")),
        "operating_margin_pct": _frac_pct(info.get("operatingMargins")),
        "roa_pct": _frac_pct(info.get("returnOnAssets")),
        "roe_pct": _frac_pct(info.get("returnOnEquity")),
        # income statement (financial_currency)
        "revenue": _i(info.get("totalRevenue")),
        "revenue_growth_pct": _frac_pct(info.get("revenueGrowth")),
        "ebitda": _i(info.get("ebitda")),
        "net_income": _i(info.get("netIncomeToCommon")),
        "earnings_growth_pct": _frac_pct(info.get("earningsQuarterlyGrowth")),
        # balance sheet & cash flow (financial_currency)
        "total_cash": _i(info.get("totalCash")),
        "total_debt": _i(info.get("totalDebt")),
        "debt_to_equity_pct": _f(info.get("debtToEquity")),  # already %
        "current_ratio": _f(info.get("currentRatio")),
        "operating_cash_flow": _i(info.get("operatingCashflow")),
        "free_cash_flow": _i(info.get("freeCashflow")),
        # share statistics
        "shares_outstanding": _i(info.get("sharesOutstanding")),
        "float_shares": _i(info.get("floatShares")),
        "held_insiders_pct": _frac_pct(info.get("heldPercentInsiders")),
        "held_institutions_pct": _frac_pct(info.get("heldPercentInstitutions")),
        "avg_volume_10d": _i(info.get("averageDailyVolume10Day")),
        # dividends
        "forward_dividend_rate": _f(info.get("dividendRate")),  # IDR/share
        "trailing_dividend_yield_pct": _frac_pct(
            info.get("trailingAnnualDividendYield")
        ),
        "five_year_avg_dividend_yield_pct": _f(
            info.get("fiveYearAvgDividendYield")
        ),  # already %
        "payout_ratio_pct": _frac_pct(info.get("payoutRatio")),
        "ex_dividend_date": _epoch_date(info.get("exDividendDate")),
        "financial_currency": (
            info.get("financialCurrency")
            if isinstance(info.get("financialCurrency"), str)
            else None
        ),
    }

    # Yahoo's precomputed price/EV ratios divide an IDR price or IDR
    # enterprise value by financial-currency figures. For USD reporters
    # (ADRO, INCO, ...) that yields nonsense like P/B 15,000x, so those
    # ratios are dropped rather than shown wrong.
    if extra["financial_currency"] not in (None, "IDR"):
        for key in ("price_to_book", "price_to_sales", "ev_to_revenue", "ev_to_ebitda"):
            extra[key] = None

    return {k: v for k, v in extra.items() if v is not None}


def _info_to_row(info: dict) -> dict:
    market_cap = info.get("marketCap")
    return {
        "market_cap": int(market_cap) if isinstance(market_cap, (int, float)) else None,
        "pe_ratio": _num(info.get("trailingPE")),
        "eps": _num(info.get("trailingEps")),
        "dividend_yield_pct": _num(info.get("dividendYield")),
        "book_value": _num(info.get("bookValue")),
        "extra": _build_extra(info) or None,
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
            missing = [k for k, v in row.items() if v is None and k != "extra"]
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
