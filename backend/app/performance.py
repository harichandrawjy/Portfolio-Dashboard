"""Daily portfolio valuation series built by replaying transactions.

RETURN METHODOLOGY (documented decision)
----------------------------------------
The value series is the raw daily market value of holdings — what the user
would see in their account. For RETURN metrics we use TIME-WEIGHTED returns
(TWR): each day's return is computed net of that day's external cash flow,

    r_d = (V_d - F_d) / V_{d-1} - 1

where F_d is the day's net flow: a buy injects (shares*price + fee) of
outside money, a sell withdraws (shares*price - fee). This model holds no
cash balance, so every trade IS an external flow.

Why TWR and not simple V_end/V_start: with simple returns a user who
deposits Rp 10M mid-month "gains" 100% on a flat market. TWR removes the
flows, measuring how the investments themselves performed — which is what
makes volatility, Sharpe and beta on this series meaningful, and is how
funds report performance (GIPS standard).

Series rules:
  - Trading calendar = the IHSG's trade dates (it is always synced, Step 3);
    if the benchmark is missing entirely, the union of the held tickers'
    dates is used instead.
  - Dates before the first transaction are skipped — there is no portfolio.
  - A ticker missing a close on a date carries its last known close
    forward. Before its first stored close exists (backfill still running),
    the most recent transaction price stands in — the user's own trade is
    a genuine price observation.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceHistory, Security, Transaction

JAKARTA = ZoneInfo("Asia/Jakarta")

RangeKey = Literal["1mo", "6mo", "1y", "all"]
RANGE_DAYS: dict[str, int] = {"1mo": 30, "6mo": 182, "1y": 365}


@dataclass
class SeriesPoint:
    date: date
    value: int          # market value, whole rupiah
    net_flow: int       # external cash flow that day (buys +, sells -)
    ihsg_close: int | None


async def build_series(
    session: AsyncSession, portfolio_id: uuid.UUID, range_key: RangeKey
) -> list[SeriesPoint]:
    txns = list(
        await session.scalars(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at, Transaction.created_at)
        )
    )
    if not txns:
        return []

    today = datetime.now(JAKARTA).date()
    first_txn_date = txns[0].executed_at
    if range_key == "all":
        start = first_txn_date
    else:
        start = max(first_txn_date, today - timedelta(days=RANGE_DAYS[range_key]))

    benchmark = await session.scalar(
        select(Security).where(Security.yahoo_symbol == "^JKSE")
    )
    sec_ids = {t.security_id for t in txns}
    all_ids = set(sec_ids)
    if benchmark is not None:
        all_ids.add(benchmark.id)

    # All closes up to today for every involved security, oldest first.
    # (Unbounded below on purpose: the carry-forward needs the last close
    # BEFORE the window too.)
    rows = await session.execute(
        select(
            PriceHistory.security_id, PriceHistory.trade_date, PriceHistory.close
        )
        .where(
            PriceHistory.security_id.in_(all_ids),
            PriceHistory.trade_date <= today,
        )
        .order_by(PriceHistory.trade_date)
    )
    closes: dict[uuid.UUID, list[tuple[date, int]]] = {}
    for sid, d, close in rows:
        closes.setdefault(sid, []).append((d, close))

    ihsg_closes = closes.get(benchmark.id, []) if benchmark is not None else []
    calendar = [d for d, _ in ihsg_closes if d >= start]
    if not calendar:  # benchmark history missing — fall back to ticker dates
        calendar = sorted(
            {d for sid in sec_ids for d, _ in closes.get(sid, []) if d >= start}
        )
    if not calendar:
        return []

    positions: dict[uuid.UUID, int] = {sid: 0 for sid in sec_ids}
    last_txn_price: dict[uuid.UUID, int] = {}
    pointers: dict[uuid.UUID, int] = {sid: 0 for sid in all_ids}
    carried: dict[uuid.UUID, int | None] = {sid: None for sid in all_ids}
    txn_i = 0
    points: list[SeriesPoint] = []

    for day in calendar:
        # Apply every transaction executed up to (and including) this day.
        # Flows land on the first trading day on/after their executed_at;
        # the very first point's flow bucket is never used by TWR (there is
        # no prior value to compute a return against).
        flow = 0
        while txn_i < len(txns) and txns[txn_i].executed_at <= day:
            t = txns[txn_i]
            if t.type == "BUY":
                positions[t.security_id] += t.shares
                flow += t.shares * t.price_per_share + t.fee
            else:
                positions[t.security_id] -= t.shares
                flow -= t.shares * t.price_per_share - t.fee
            last_txn_price[t.security_id] = t.price_per_share
            txn_i += 1

        # Advance each security's carried close to this day, then value it.
        value = 0
        for sid in sec_ids:
            sec_closes = closes.get(sid, [])
            while (
                pointers[sid] < len(sec_closes)
                and sec_closes[pointers[sid]][0] <= day
            ):
                carried[sid] = sec_closes[pointers[sid]][1]
                pointers[sid] += 1
            shares = positions[sid]
            if shares <= 0:
                continue
            price = carried[sid]
            if price is None:  # no stored close yet — use own trade price
                price = last_txn_price.get(sid)
            if price is not None:
                value += shares * price

        ihsg_close = None
        if benchmark is not None:
            bid = benchmark.id
            while (
                pointers[bid] < len(ihsg_closes)
                and ihsg_closes[pointers[bid]][0] <= day
            ):
                carried[bid] = ihsg_closes[pointers[bid]][1]
                pointers[bid] += 1
            ihsg_close = carried[bid]

        points.append(SeriesPoint(day, value, flow, ihsg_close))

    return points


def time_weighted_returns(points: list[SeriesPoint]) -> list[float]:
    """Daily TWR series: r_d = (V_d - F_d) / V_{d-1} - 1.

    Days whose prior value is zero are skipped (nothing was invested, so
    no return is defined — e.g. right after a full liquidation).
    """
    out: list[float] = []
    for prev, cur in zip(points, points[1:]):
        if prev.value > 0:
            out.append((cur.value - cur.net_flow) / prev.value - 1)
    return out


def aligned_benchmark_pairs(
    points: list[SeriesPoint],
) -> tuple[list[float], list[float]]:
    """(portfolio TWR, benchmark return) pairs for the days where BOTH are
    computable — this alignment is what analytics.beta() requires."""
    port: list[float] = []
    bench: list[float] = []
    for prev, cur in zip(points, points[1:]):
        if prev.value > 0 and prev.ihsg_close and cur.ihsg_close:
            port.append((cur.value - cur.net_flow) / prev.value - 1)
            bench.append(cur.ihsg_close / prev.ihsg_close - 1)
    return port, bench
