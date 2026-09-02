"""Integration test for /performance and /metrics.

Fixture world (all values chosen so the arithmetic is checkable by eye):

  Ten IDX trading days, Mon 2026-06-01 .. Fri 2026-06-12 (weekends absent).

  AAAA closes: 1000, 1010, 1020, ... +10 per day ... 1090
  BBBB closes: flat 2000 — and NO row on Jun 4 (tests carry-forward)
  IHSG closes: 7000, 7070, 7140, ... +70 per day (i.e. +1% of 7000 daily),
               plus two rows in late May that predate the first transaction —
               the series must skip them.

  Transactions:
    Jun 1   BUY  1 lot (100 shares) AAAA @ 1000
    Jun 3   BUY  1 lot BBBB @ 2000
    Jun 10  SELL 1 lot AAAA @ 1070   (position goes to zero)

  Expected daily HOLDINGS value (hand-computed):
    Jun  1: 100*1000                    = 100_000
    Jun  2: 100*1010                    = 101_000
    Jun  3: 100*1020 + 100*2000        = 302_000
    Jun  4: 100*1030 + 100*2000(carry) = 303_000
    Jun  5: 100*1040 + 200_000         = 304_000
    Jun  8: 100*1050 + 200_000         = 305_000
    Jun  9: 100*1060 + 200_000         = 306_000
    Jun 10: sold AAAA ->  100*2000     = 200_000
    Jun 11:                              200_000
    Jun 12:                              200_000

  That value series is what TWR and the risk metrics consume. The CHART
  plots the cumulative time-weighted return chained off it, and the IHSG
  leg is the index's own return from 7000 — both starting at 0.
"""

from datetime import date

import pytest

from tests.helpers import fund, register_verified

pytestmark = pytest.mark.asyncio(loop_scope="session")

TRADING_DAYS = [
    date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4),
    date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10),
    date(2026, 6, 11), date(2026, 6, 12),
]

# Market value of HOLDINGS. This is what TWR and every risk metric use, and
# it is what the chart used to plot on its own — which is why selling looked
# like losing: on Jun 10 holdings fall 306_000 -> 200_000 while the account
# is worth more than it was.
EXPECTED_VALUES = [
    100_000, 101_000, 302_000, 303_000, 304_000,
    305_000, 306_000, 200_000, 200_000, 200_000,
]

# The chart: cumulative time-weighted return, in percent, from 0 on Jun 1.
# Each day's factor is (value - that day's flow) / yesterday's value, so the
# 200_000 spent on BBBB and the 107_000 returned by the AAAA sale both cancel
# out of the day they land on. Chained by hand:
#
#   Jun  2  101/100                                  = 1.01     -> +1.0000%
#   Jun  3  * (302_000 - 200_000 bought)/101_000     = 1.02     -> +2.0000%
#   Jun  4  * 303/302                                           -> +2.3377%
#   Jun  5  * 304/303                                           -> +2.6755%
#   Jun  8  * 305/304                                           -> +3.0132%
#   Jun  9  * 306/305   (telescopes to 1.02 * 306/302)          -> +3.3510%
#   Jun 10  * (200_000 + 107_000 sold)/306_000 = 1.02 * 307/302 -> +3.6887%
#   Jun 11  nothing moves, and nothing was bought or sold       -> +3.6887%
#   Jun 12                                                      -> +3.6887%
#
# Note Jun 3 and Jun 10: doubling the invested money and then liquidating
# half of it move the line by the underlying stocks' own 1% steps and nothing
# else. That is the whole reason the chart is a return.
EXPECTED_RETURN_PCT = [
    0.0, 1.0, 2.0, 2.3377, 2.6755, 3.0132, 3.3510, 3.6887, 3.6887, 3.6887,
]

# IHSG rises exactly 1% of 7000 per day, so its return is 1% per step.
EXPECTED_IHSG_PCT = [1.0 * i for i in range(10)]


async def _seed_synthetic_market():
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import PriceHistory, Security

    async with SessionLocal() as session:
        async with session.begin():
            aaaa = Security(ticker="AAAA", yahoo_symbol="AAAA.JK",
                            name="Synthetic Alpha Tbk.", kind="stock")
            bbbb = Security(ticker="BBBB", yahoo_symbol="BBBB.JK",
                            name="Synthetic Beta Tbk.", kind="stock")
            session.add_all([aaaa, bbbb])
            await session.flush()

            ihsg_id = await session.scalar(
                select(Security.id).where(Security.yahoo_symbol == "^JKSE")
            )

            for i, day in enumerate(TRADING_DAYS):
                session.add(PriceHistory(
                    security_id=aaaa.id, trade_date=day, close=1000 + 10 * i))
                if day != date(2026, 6, 4):  # BBBB's missing day
                    session.add(PriceHistory(
                        security_id=bbbb.id, trade_date=day, close=2000))
                session.add(PriceHistory(
                    security_id=ihsg_id, trade_date=day, close=7000 + 70 * i))

            # benchmark data BEFORE the first transaction — must be skipped
            session.add(PriceHistory(
                security_id=ihsg_id, trade_date=date(2026, 5, 28), close=6900))
            session.add(PriceHistory(
                security_id=ihsg_id, trade_date=date(2026, 5, 29), close=6950))


async def _login(client, email):
    """Register, verify and sign in. See helpers.register_verified."""
    return await register_verified(client, email, "password-123")


async def test_performance_series_and_metrics(client):
    await _seed_synthetic_market()
    auth = await _login(client, "fajar@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Backtest"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)

    for txn in (
        {"ticker": "AAAA", "type": "BUY", "lots": 1, "price_per_share": 1000,
         "fee": 0, "executed_at": "2026-06-01"},
        {"ticker": "BBBB", "type": "BUY", "lots": 1, "price_per_share": 2000,
         "fee": 0, "executed_at": "2026-06-03"},
        {"ticker": "AAAA", "type": "SELL", "lots": 1, "price_per_share": 1070,
         "fee": 0, "executed_at": "2026-06-10"},
    ):
        r = await client.post(
            f"/portfolios/{pid}/transactions", json=txn, headers=auth
        )
        assert r.status_code == 201

    # ------------------------------------------------------------------
    # /performance
    # ------------------------------------------------------------------
    r = await client.get(f"/portfolios/{pid}/performance?range=all", headers=auth)
    assert r.status_code == 200
    points = r.json()["points"]

    # ten points, starting at the first transaction — late-May IHSG skipped
    assert [p["date"] for p in points] == [d.isoformat() for d in TRADING_DAYS]
    assert [p["return_pct"] for p in points] == pytest.approx(
        EXPECTED_RETURN_PCT, abs=1e-3
    )
    assert [p["ihsg_return_pct"] for p in points] == pytest.approx(
        EXPECTED_IHSG_PCT, abs=1e-9
    )

    # ------------------------------------------------------------------
    # /metrics
    # ------------------------------------------------------------------
    r = await client.get(f"/portfolios/{pid}/metrics?range=all", headers=auth)
    assert r.status_code == 200
    m = r.json()

    assert m["trading_days"] == 10
    assert m["start_date"] == "2026-06-01"
    assert m["end_date"] == "2026-06-12"

    # Time-weighted total return, telescoped by hand:
    #   r(Jun2)  = 101/100
    #   r(Jun3)  = (302_000 - 200_000 flow) / 101_000 = 102/101
    #   r(Jun4..Jun9) chain to 306/302
    #   r(Jun10) = (200_000 + 107_000 sale) / 306_000 = 307/306
    #   r(Jun11) = r(Jun12) = 1
    #   total = 1.01 * 102/101 * 307/302 - 1 = 0.0368874 -> 3.69%
    assert m["total_return_pct"] == pytest.approx(3.69, abs=0.01)

    # Same chain, same flows: the card and the chart's last point are one
    # number. If these ever drift apart, one of the two is lying on screen.
    assert m["total_return_pct"] == pytest.approx(points[-1]["return_pct"], abs=0.01)
    assert m["benchmark_return_pct"] == pytest.approx(
        points[-1]["ihsg_return_pct"], abs=0.01
    )

    # IHSG went 7000 -> 7630 = +9.0%
    assert m["benchmark_return_pct"] == pytest.approx(9.0, abs=0.01)

    # every daily TWR is >= 0, so the growth index never dips: drawdown 0
    assert m["max_drawdown_pct"] == 0.0

    assert m["annualized_volatility_pct"] is not None
    assert m["sharpe_ratio"] is not None
    assert m["beta"] is not None
    assert m["risk_free_rate_pct"] == 5.5


async def test_cumulative_returns_chains_the_same_way_metrics_do():
    """The chart series against the hand-computed table above, with nothing
    else in the loop. Both endpoints have to agree on screen, so they are
    built from one chain: this pins that the chart is `time_weighted_returns`
    accumulated, and that every flow cancels out of the day it lands on."""
    from app.performance import (
        SeriesPoint,
        cumulative_returns,
        time_weighted_returns,
    )

    flows = {0: 100_000, 2: 200_000, 7: -107_000}  # opening buy, BBBB, sale
    points = [
        SeriesPoint(day, value, flows.get(i, 0), 7000 + 70 * i)
        for i, (day, value) in enumerate(zip(TRADING_DAYS, EXPECTED_VALUES))
    ]

    chart = cumulative_returns(points)
    assert [r * 100 for r in chart] == pytest.approx(EXPECTED_RETURN_PCT, abs=1e-3)

    index = 1.0
    for r in time_weighted_returns(points):
        index *= 1 + r
    assert index - 1 == pytest.approx(chart[-1])


async def test_a_liquidated_portfolio_holds_its_line_flat():
    """Once holdings are zero there is no return to earn, so the line carries
    forward rather than falling to zero or vanishing. `time_weighted_returns`
    drops those days instead — a run of zeroes would deflate the volatility
    it feeds — which is why the chart has its own accumulator."""
    from app.performance import SeriesPoint, cumulative_returns

    points = [
        SeriesPoint(TRADING_DAYS[0], 100_000, 100_000, None),
        SeriesPoint(TRADING_DAYS[1], 110_000, 0, None),
        SeriesPoint(TRADING_DAYS[2], 0, -110_000, None),  # sold the lot
        SeriesPoint(TRADING_DAYS[3], 0, 0, None),
    ]
    assert cumulative_returns(points) == pytest.approx([0.0, 0.1, 0.1, 0.1])


async def test_performance_empty_portfolio(client):
    auth = await _login(client, "gita@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Empty"}, headers=auth)
    ).json()["id"]

    r = await client.get(f"/portfolios/{pid}/performance?range=all", headers=auth)
    assert r.status_code == 200
    assert r.json()["points"] == []

    r = await client.get(f"/portfolios/{pid}/metrics?range=all", headers=auth)
    assert r.status_code == 200
    m = r.json()
    assert m["trading_days"] == 0
    assert m["total_return_pct"] is None
    assert m["beta"] is None


async def test_performance_invalid_range_rejected(client):
    auth = await _login(client, "hana@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Ranges"}, headers=auth)
    ).json()["id"]
    r = await client.get(
        f"/portfolios/{pid}/performance?range=fortnight", headers=auth
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# No movement of money may move the line
#
# Four rupiah versions of this chart failed here first, each fixing the last
# one's artifact and introducing its own (the progression is written up in
# app/performance.py). Plotting return instead closes the whole class: a flow
# is subtracted from the day it lands on, so there is no arrangement of
# deposits, sales or same-day rotations that can register as performance.
#
# These use the synthetic June market seeded above, which has ten trading
# days. Using BBCA and July dates looked fine but collapsed onto a single
# calendar point, because the only IHSG bar in that range is 17 July.
# ---------------------------------------------------------------------------

async def _funded(client, email: str, name: str, amount: int):
    from .helpers import fund, register_verified

    auth = await register_verified(client, email, "password-123")
    pid = (
        await client.post("/portfolios", json={"name": name}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid, amount)
    return auth, pid


async def _trade(client, auth, pid, ticker, kind, lots, price, day):
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": ticker, "type": kind, "lots": lots,
            "price_per_share": price, "fee": 0, "executed_at": day,
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text


async def _chart(client, auth, pid):
    body = (
        await client.get(f"/portfolios/{pid}/performance?range=all", headers=auth)
    ).json()
    return {p["date"]: p["return_pct"] for p in body["points"]}


async def test_selling_everything_does_not_send_the_chart_to_zero(client):
    """Holdings go to zero on Jun 10; the return earned getting there does
    not. The rupiah chart drew a cliff here because the proceeds stopped
    being plotted."""
    auth, pid = await _funded(client, "liquidate@example.com", "Liquidated", 10_000_000)
    await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")
    await _trade(client, auth, pid, "AAAA", "SELL", 1, 1070, "2026-06-10")

    values = await _chart(client, auth, pid)
    assert values, "no points"
    # Bought at 1000, sold at 1070: +7%, and it stays there while the money
    # sits out of the market.
    assert values["2026-06-10"] == pytest.approx(7.0)
    assert values["2026-06-12"] == pytest.approx(7.0)
    assert min(values.values()) == 0.0  # the start, and never below it


async def test_a_same_day_sell_and_rebuy_is_not_counted_twice(client):
    """The reported bug. Selling PANI and buying ESSA on one day, with the
    buy recorded FIRST, showed the new holding plus the proceeds that paid
    for it. The day's flows are one bucket, so the order cannot matter."""
    auth, pid = await _funded(client, "sameday@example.com", "Rotated", 10_000_000)
    await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")
    # Recorded buy-first, exactly as the real portfolio was entered.
    await _trade(client, auth, pid, "BBBB", "BUY", 1, 2000, "2026-06-10")
    await _trade(client, auth, pid, "AAAA", "SELL", 1, 1070, "2026-06-10")

    values = await _chart(client, auth, pid)
    # AAAA earned 7% before being rotated into BBBB, which is flat for the
    # rest of the window. Rotating is not a gain, so the answer is the same
    # +7% a plain liquidation gives.
    assert values["2026-06-10"] == pytest.approx(7.0)
    assert values["2026-06-12"] == pytest.approx(7.0)


async def test_the_size_of_a_deposit_does_not_move_the_chart(client):
    """Funding an account is not performance. Two portfolios that make the
    same trade draw the same line however differently they are funded — the
    version that plotted holdings plus the cash balance failed this."""
    auth, small = await _funded(
        client, "idlecash@example.com", "Barely funded", 1_000_000
    )
    big = (
        await client.post("/portfolios", json={"name": "Overfunded"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, big, 500_000_000)

    for pid in (small, big):
        await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")

    line = await _chart(client, auth, small)
    assert line == await _chart(client, auth, big)
    # AAAA closed 1000 on Jun 1 and 1090 on Jun 12: the line is the stock and
    # nothing else. The other ~499,900,000 never appears.
    assert line["2026-06-12"] == pytest.approx(9.0)


async def test_putting_new_capital_to_work_does_not_step_the_line(client):
    """The last of the four. Depositing and then buying tripled the plotted
    figure while IHSG stayed flat, because the new holding arrived as value
    with nothing subtracted for what paid for it."""
    auth, pid = await _funded(client, "newcapital@example.com", "Topped up", 10_000_000)
    await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")
    await _trade(client, auth, pid, "BBBB", "BUY", 1, 2000, "2026-06-03")

    values = await _chart(client, auth, pid)
    # Jun 3 doubles the money invested. BBBB is flat all window, so the line
    # may only show AAAA's own step, 1010 -> 1020, chained onto Jun 2's 1%.
    assert values["2026-06-02"] == pytest.approx(1.0)
    assert values["2026-06-03"] == pytest.approx(2.0)
