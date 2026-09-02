"""Daily portfolio valuation series built by replaying transactions.

RETURN METHODOLOGY (documented decision)
----------------------------------------
The value series is the raw daily market value of holdings — what the user
would see in their account. For RETURN metrics we use TIME-WEIGHTED returns
(TWR): each day's return is computed net of that day's external cash flow,

    r_d = (V_d - F_d) / V_{d-1} - 1

where F_d is the day's net flow: a buy injects (shares*price + fee) of
outside money, a sell withdraws (shares*price - fee). Trades are treated
as external flows because analytics deliberately measure INVESTED capital
only. (The optional cash ledger added in migration 0004 is a budgeting
device for sizing buys; idle cash is excluded from the performance series
and metrics on purpose.)

Why TWR and not simple V_end/V_start: with simple returns a user who
deposits Rp 10M mid-month "gains" 100% on a flat market. TWR removes the
flows, measuring how the investments themselves performed — which is what
makes volatility, Sharpe and beta on this series meaningful, and is how
funds report performance (GIPS standard).

THE CHART PLOTS RETURN, NOT RUPIAH, and that took four attempts to get
right. Every one of them failed the same way: a rupiah line answers "what is
this worth", which moves when money moves, so laying a benchmark over it
compares a quantity of money against an index.

    holdings alone            a sale moved money somewhere unplotted, so
                              selling read as a loss and liquidating drew a
                              line to zero
    holdings + cash           fixed that, and then funding the account made
                              the line jump, which is not performance either
    + recycled proceeds       counted only money that had been through the
                              market, but applying trades one at a time made
                              the recorded order of same-day trades
                              load-bearing: a buy entered before the sale
                              that funded it showed the holding AND the
                              proceeds that bought it
    + netting the day         closed that, and new capital still stepped the
                              line, because it arrives as holdings

Cumulative TWR has no such seam. Deposits, withdrawals, sales and rotations
are all netted out of the day they land on, by the same formula the metrics
already use — so the chart's last point IS the reported total return, and
the benchmark overlay compares two returns rather than a value against an
index. The rupiah figure was never lost: it is the largest number on the
page, in the portfolio's own summary.

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
    value: int          # market value of HOLDINGS, whole rupiah
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
        #
        # One bucket for the whole day, not one per trade. `executed_at` is a
        # DATE, so a sell and the buy it funded are simultaneous here and the
        # recorded order is only whatever order the user typed them in.
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


def cumulative_returns(points: list[SeriesPoint]) -> list[float]:
    """Growth of the invested money since the first point, as a fraction.

    One value per point, starting at 0.0 — this is the chart series, so every
    date needs a value. It is the same chain the metrics endpoint builds from
    `time_weighted_returns`, which means the last element of this list IS the
    reported total return, and the two can never disagree on screen.

    A day whose predecessor held nothing carries the line forward flat rather
    than being dropped. After a full liquidation there is no return to earn:
    the money is out of the market, and holding the last level says exactly
    that. `time_weighted_returns` omits those days instead, because a run of
    zeroes would deflate the volatility it feeds.
    """
    out = [0.0]
    index = 1.0
    for prev, cur in zip(points, points[1:]):
        if prev.value > 0:
            index *= (cur.value - cur.net_flow) / prev.value
        out.append(index - 1)
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
