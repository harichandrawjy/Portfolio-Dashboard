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

from tests.helpers import fund

pytestmark = pytest.mark.asyncio(loop_scope="session")

TRADING_DAYS = [
    date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4),
    date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10),
    date(2026, 6, 11), date(2026, 6, 12),
]

EXPECTED_VALUES = [
    100_000, 101_000, 302_000, 303_000, 304_000,
    305_000, 306_000, 200_000, 200_000, 200_000,
]

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
    await client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    r = await client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


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
    assert [p["portfolio_value"] for p in points] == EXPECTED_VALUES
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
