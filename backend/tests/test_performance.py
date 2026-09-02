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

  Expected daily portfolio value (hand-computed):
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

  IHSG normalized to the portfolio's start (100_000 at 7000):
    7000 -> 100_000, 7070 -> 101_000, ... +1_000 per day ... 109_000
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

# Proceeds not yet redeployed. The 10bn deposit contributes NOTHING — an
# idle deposit is not part of the investment programme. Only the Jun 10 sale
# puts money in this pool, and nothing buys it back.
EXPECTED_IDLE = [0] * 7 + [107_000] * 3

# The chart plots holdings plus that pool. Note Jun 10: holdings fall
# 306_000 -> 200_000 but the chart holds at 307_000, because the 107_000 of
# proceeds is still money at work. That is the whole point.
EXPECTED_CHART = [h + c for h, c in zip(EXPECTED_VALUES, EXPECTED_IDLE)]

EXPECTED_IHSG_NORM = [100_000 + 1_000 * i for i in range(10)]


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
    assert [p["portfolio_value"] for p in points] == EXPECTED_CHART
    assert [p["ihsg_normalized"] for p in points] == EXPECTED_IHSG_NORM

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
    #   total = 1.01 * 102/101 * 307/302 - 1 = 0.036786 -> 3.68%
    assert m["total_return_pct"] == pytest.approx(3.68, abs=0.01)

    # IHSG went 7000 -> 7630 = +9.0%
    assert m["benchmark_return_pct"] == pytest.approx(9.0, abs=0.01)

    # every daily TWR is >= 0, so the growth index never dips: drawdown 0
    assert m["max_drawdown_pct"] == 0.0

    assert m["annualized_volatility_pct"] is not None
    assert m["sharpe_ratio"] is not None
    assert m["beta"] is not None
    assert m["risk_free_rate_pct"] == 5.5


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
# Selling must not look like losing, and depositing must not look like winning
#
# The chart plots holdings plus proceeds not yet redeployed. Three failures
# had to be closed, and the first two pull in opposite directions:
#
#   holdings alone            a sale moved money somewhere unplotted, so
#                             selling read as a loss and liquidating a
#                             portfolio drew a line to zero
#   holdings + cash balance   fixed that, but funding an account then made
#                             the line jump, which is not performance either
#   per-trade pool accounting fixed both, but made the recorded order of
#                             same-day trades load-bearing: a buy entered
#                             before the sale that funded it consumed an
#                             empty pool, and the sale then credited a pool
#                             nothing spent — the chart showed the holding
#                             AND the money that bought it
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
    return {p["date"]: p["portfolio_value"] for p in body["points"]}


async def test_selling_everything_does_not_send_the_chart_to_zero(client):
    auth, pid = await _funded(client, "liquidate@example.com", "Liquidated", 10_000_000)
    await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")
    await _trade(client, auth, pid, "AAAA", "SELL", 1, 1070, "2026-06-10")

    values = await _chart(client, auth, pid)
    assert values, "no points"
    # Holdings are zero from Jun 10, but the 107_000 the position returned is
    # still money at work — the line holds instead of falling off a cliff.
    assert values["2026-06-12"] == 107_000, values
    assert min(values.values()) > 0, values


async def test_a_same_day_sell_and_rebuy_is_not_counted_twice(client):
    """The reported bug. Selling PANI and buying ESSA on one day, with the
    buy recorded FIRST, showed the new holding plus the proceeds that paid
    for it. Netting the day makes the recorded order irrelevant."""
    auth, pid = await _funded(client, "sameday@example.com", "Rotated", 10_000_000)
    await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")
    # Recorded buy-first, exactly as the real portfolio was entered.
    await _trade(client, auth, pid, "BBBB", "BUY", 1, 2000, "2026-06-10")
    await _trade(client, auth, pid, "AAAA", "SELL", 1, 1070, "2026-06-10")

    values = await _chart(client, auth, pid)
    # After the rotation the portfolio holds only BBBB, worth 200_000. The
    # 107_000 of proceeds went into it, so it must NOT also be added on top.
    assert values["2026-06-12"] == 200_000, values


async def test_an_idle_deposit_does_not_move_the_chart(client):
    """Funding an account is not performance, so a large idle balance stays
    invisible until it actually buys something."""
    auth, pid = await _funded(client, "idlecash@example.com", "Mostly idle", 500_000_000)
    await _trade(client, auth, pid, "AAAA", "BUY", 1, 1000, "2026-06-01")

    values = await _chart(client, auth, pid)
    # One lot of AAAA, which closes between 1000 and 1110 across the window.
    # The other ~499,900,000 sitting in cash contributes nothing.
    assert max(values.values()) <= 111_000, values
