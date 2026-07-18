"""Per-ticker stat cache (security_stats), computed off the request path.

WHY A CACHE TABLE: the stock detail page shows ~12 statistics derived from
up to ~1,250 daily bars. Recomputing them on every page load would rescan
price_history per request for numbers that only change once a day. Instead
the nightly price job (and the tail end of every first-use backfill) calls
refresh_stats(), and the page read is a single-row primary-key lookup.

All statistical measures reuse the pure functions from app.analytics
unchanged — the same code that powers portfolio metrics.

Window conventions (documented for the README):
  - 1D/1W/1M/YTD/1Y returns: strict calendar windows; the base is the
    latest close ON OR BEFORE the window start (None if none exists).
  - 5Y return: over all stored history — the lazy backfill window itself
    caps storage at ~5 years, so "since data start" is the honest label.
  - 52-week high/low: intraday basis where high/low columns exist,
    closing basis otherwise. All-time = all stored history.
  - Volatility, max drawdown, beta: closing basis over the last 365 days;
    beta pairs stock and IHSG returns on shared trading dates only.
"""

import logging
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.analytics import annualized_volatility, beta, daily_returns, max_drawdown
from app.db import SessionLocal
from app.models import PriceHistory, Security, SecurityStats
from app.sync.universe import BENCHMARK

logger = logging.getLogger(__name__)


@dataclass
class Bar:
    day: date
    close: int
    high: int | None
    low: int | None
    volume: int | None


def _round4(x: float | None) -> Decimal | None:
    return None if x is None else Decimal(f"{x:.4f}")


def compute_stats(bars: list[Bar], ihsg_by_date: dict[date, int]) -> dict:
    """Pure computation over one ticker's bars; returns column values."""
    dates = [b.day for b in bars]
    closes = [b.close for b in bars]
    last_date, last_close = dates[-1], closes[-1]

    def base_on_or_before(cutoff: date) -> int | None:
        idx = bisect_right(dates, cutoff) - 1
        return closes[idx] if idx >= 0 else None

    def simple_ret(base: int | None) -> float | None:
        return None if not base else (last_close / base - 1) * 100

    return_1d = simple_ret(closes[-2]) if len(closes) >= 2 else None
    return_1w = simple_ret(base_on_or_before(last_date - timedelta(days=7)))
    return_1mo = simple_ret(base_on_or_before(last_date - timedelta(days=30)))
    return_1y = simple_ret(base_on_or_before(last_date - timedelta(days=365)))
    # YTD base: last close of the previous calendar year
    ytd_idx = bisect_left(dates, date(last_date.year, 1, 1)) - 1
    return_ytd = simple_ret(closes[ytd_idx]) if ytd_idx >= 0 else None
    # 5Y: over all stored history (backfill window == storage horizon)
    return_5y = simple_ret(closes[0]) if len(closes) >= 2 else None

    def hi_lo(window: list[Bar]) -> tuple[int | None, int | None]:
        if not window:
            return None, None
        highs = [b.high if b.high is not None else b.close for b in window]
        lows = [b.low if b.low is not None else b.close for b in window]
        return max(highs), min(lows)

    year_ago = last_date - timedelta(days=365)
    high_52w, low_52w = hi_lo([b for b in bars if b.day > year_ago])
    high_all, low_all = hi_lo(bars)

    vol_window = [b.volume for b in bars if b.day > last_date - timedelta(days=91)]
    vols = [v for v in vol_window if v is not None]
    avg_volume_3mo = round(sum(vols) / len(vols)) if vols else None

    closes_1y = [b.close for b in bars if b.day > year_ago]
    returns_1y = daily_returns(closes_1y)
    volatility = annualized_volatility(returns_1y)
    drawdown = max_drawdown(closes_1y)

    # Beta: stock vs IHSG on their common trading dates within the year
    common = [
        (b.close, ihsg_by_date[b.day])
        for b in bars
        if b.day > year_ago and b.day in ihsg_by_date
    ]
    beta_1y = None
    if len(common) >= 3:
        stock_r = daily_returns([c for c, _ in common])
        bench_r = daily_returns([i for _, i in common])
        beta_1y = beta(stock_r, bench_r)

    return {
        "return_1d_pct": _round4(return_1d),
        "return_1w_pct": _round4(return_1w),
        "return_1mo_pct": _round4(return_1mo),
        "return_ytd_pct": _round4(return_ytd),
        "return_1y_pct": _round4(return_1y),
        "return_5y_pct": _round4(return_5y),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "high_all": high_all,
        "low_all": low_all,
        "avg_volume_3mo": avg_volume_3mo,
        "volatility_1y_pct": _round4(None if volatility is None else volatility * 100),
        "max_drawdown_1y_pct": _round4(None if drawdown is None else drawdown * 100),
        "beta_1y": _round4(beta_1y),
    }


async def refresh_stats(security_ids: list | None = None) -> int:
    """Recompute cached stats for tracked stocks (or just the ids given)."""
    updated = 0
    async with SessionLocal() as session:
        async with session.begin():
            benchmark_id = await session.scalar(
                select(Security.id).where(
                    Security.yahoo_symbol == BENCHMARK["yahoo_symbol"]
                )
            )

            tracked_q = (
                select(PriceHistory.security_id)
                .join(Security, Security.id == PriceHistory.security_id)
                .where(Security.kind == "stock")
                .distinct()
            )
            tracked = set((await session.execute(tracked_q)).scalars().all())
            if security_ids is not None:
                tracked &= set(security_ids)
            if not tracked:
                return 0

            ihsg_by_date: dict[date, int] = {}
            if benchmark_id is not None:
                rows = await session.execute(
                    select(PriceHistory.trade_date, PriceHistory.close).where(
                        PriceHistory.security_id == benchmark_id
                    )
                )
                ihsg_by_date = {d: c for d, c in rows}

            for sid in tracked:
                rows = await session.execute(
                    select(
                        PriceHistory.trade_date,
                        PriceHistory.close,
                        PriceHistory.high,
                        PriceHistory.low,
                        PriceHistory.volume,
                    )
                    .where(PriceHistory.security_id == sid)
                    .order_by(PriceHistory.trade_date)
                )
                bars = [Bar(*r) for r in rows]
                if not bars:
                    continue
                values = compute_stats(bars, ihsg_by_date)
                stmt = pg_insert(SecurityStats).values(
                    security_id=sid, computed_at=func.now(), **values
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["security_id"],
                    set_={"computed_at": func.now(), **values},
                )
                await session.execute(stmt)
                updated += 1

    logger.info("security stats refreshed for %d ticker(s)", updated)
    return updated
