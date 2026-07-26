"""Stock detail endpoints + the security_stats cache, hand-checked.

BBCA fixture series (conftest already holds the Jul 17 bar):

  date        close   high    low     volume
  Jul  6      6800    6850    6750    1,000,000
  Jul  7      6900    6950    6850    1,000,000
  Jul  8      6850    6900    6800    1,000,000
  Jul  9      6900    6950    6850    1,000,000
  Jul 10      6950    7000    6900    1,000,000
  Jul 13      7100    7150    7050    1,000,000
  Jul 14      7050    7100    7000    1,000,000
  Jul 15      7200    7250    7150    2,000,000
  Jul 16      6860    6910    6810    1,500,000
  Jul 17      7000    7050    6850    1,000,000   <- from conftest

Hand-computed expectations:
  1D return   7000/6860 - 1              = +2.0408%
  1W return   base = close on/before Jul 10 = 6950 -> 7000/6950 - 1 = +0.7194%
  1M / YTD / 1Y                          = None (series starts Jul 6)
  5Y (stored history) 7000/6800 - 1      = +2.9412%
  52w high = max(high) = 7250 (Jul 15); 52w low = min(low) = 6750 (Jul 6)
  all-time high/low = same (only data)
  avg volume = (8x1.0M + 2.0M + 1.5M) / 10 = 1,150,000
  max drawdown = trough 6860 after peak 7200: 6860/7200 - 1 = -4.7222%
  volatility & beta: wire-checked against the (separately hand-tested)
  pure functions on the exact same series.
"""

from datetime import date

import pytest

from app.analytics import annualized_volatility, beta, daily_returns
from tests.helpers import fund

pytestmark = pytest.mark.asyncio(loop_scope="session")

BBCA_ROWS = [
    (date(2026, 7, 6), 6800, 6850, 6750, 1_000_000),
    (date(2026, 7, 7), 6900, 6950, 6850, 1_000_000),
    (date(2026, 7, 8), 6850, 6900, 6800, 1_000_000),
    (date(2026, 7, 9), 6900, 6950, 6850, 1_000_000),
    (date(2026, 7, 10), 6950, 7000, 6900, 1_000_000),
    (date(2026, 7, 13), 7100, 7150, 7050, 1_000_000),
    (date(2026, 7, 14), 7050, 7100, 7000, 1_000_000),
    (date(2026, 7, 15), 7200, 7250, 7150, 2_000_000),
    (date(2026, 7, 16), 6860, 6910, 6810, 1_500_000),
]

IHSG_ROWS = [
    (date(2026, 7, 6), 7900),
    (date(2026, 7, 7), 7950),
    (date(2026, 7, 8), 7925),
    (date(2026, 7, 9), 7960),
    (date(2026, 7, 10), 7980),
    (date(2026, 7, 13), 8050),
    (date(2026, 7, 14), 8020),
    (date(2026, 7, 15), 8100),
    (date(2026, 7, 16), 7950),
    (date(2026, 7, 17), 8000),
]

BBCA_CLOSES = [r[1] for r in BBCA_ROWS] + [7000]
IHSG_CLOSES = [r[1] for r in IHSG_ROWS]


async def _seed_price_series():
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import PriceHistory, Security

    async with SessionLocal() as session:
        async with session.begin():
            bbca_id = await session.scalar(
                select(Security.id).where(Security.ticker == "BBCA")
            )
            ihsg_id = await session.scalar(
                select(Security.id).where(Security.yahoo_symbol == "^JKSE")
            )
            for d, c, h, lo, v in BBCA_ROWS:
                session.add(PriceHistory(
                    security_id=bbca_id, trade_date=d,
                    close=c, high=h, low=lo, volume=v,
                ))
            for d, c in IHSG_ROWS:
                session.add(PriceHistory(security_id=ihsg_id, trade_date=d, close=c))


async def _login(client, email):
    await client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    r = await client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_stats_match_hand_checked_values(client):
    await _seed_price_series()

    from app.sync.stats import refresh_stats

    assert await refresh_stats() >= 1

    auth = await _login(client, "putra@example.com")
    r = await client.get("/securities/BBCA", headers=auth)
    assert r.status_code == 200
    body = r.json()

    assert body["name"] == "Bank Central Asia Tbk."
    assert body["sector"] == "Keuangan"
    assert body["has_history"] is True
    assert body["quote_price"] == 7000  # seeded latest_quotes row
    assert body["last_close"] == 7000
    assert body["last_close_date"] == "2026-07-17"

    s = body["stats"]
    assert s is not None
    assert s["return_1d_pct"] == pytest.approx(2.0408, abs=1e-4)
    assert s["return_1w_pct"] == pytest.approx(0.7194, abs=1e-4)
    assert s["return_1mo_pct"] is None
    assert s["return_ytd_pct"] is None
    assert s["return_1y_pct"] is None
    assert s["return_5y_pct"] == pytest.approx(2.9412, abs=1e-4)
    assert s["high_52w"] == 7250
    assert s["low_52w"] == 6750
    assert s["high_all"] == 7250
    assert s["low_all"] == 6750
    assert s["avg_volume_3mo"] == 1_150_000
    assert s["max_drawdown_1y_pct"] == pytest.approx(-4.7222, abs=1e-4)

    # volatility & beta wired through the hand-tested pure functions
    expected_vol = annualized_volatility(daily_returns(BBCA_CLOSES)) * 100
    assert s["volatility_1y_pct"] == pytest.approx(expected_vol, abs=1e-3)
    expected_beta = beta(daily_returns(BBCA_CLOSES), daily_returns(IHSG_CLOSES))
    assert s["beta_1y"] == pytest.approx(expected_beta, abs=1e-3)


async def test_prices_series_with_ihsg_overlay(client):
    auth = await _login(client, "qori@example.com")
    r = await client.get("/securities/BBCA/prices?range=all", headers=auth)
    assert r.status_code == 200
    points = r.json()["points"]

    assert len(points) == 10
    assert points[0] == {
        "date": "2026-07-06", "open": None, "high": 6850, "low": 6750,
        "close": 6800, "volume": 1_000_000, "ihsg": 6800,
    }
    # IHSG rebased to the stock's first close: 8000/7900 * 6800 = 6886.08
    assert points[-1]["close"] == 7000
    assert points[-1]["ihsg"] == 6886


async def test_detail_for_no_history_and_unknown(client):
    auth = await _login(client, "rani@example.com")

    # TLKM: in the universe, zero price rows -> the page's backfill trigger
    r = await client.get("/securities/TLKM", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["has_history"] is False
    assert body["stats"] is None
    assert body["last_close"] is None

    assert (await client.get("/securities/XXXX", headers=auth)).status_code == 404
    # the IHSG index row is not a stock page
    assert (await client.get("/securities/IHSG", headers=auth)).status_code == 404


async def test_position_panel_and_markers(client):
    auth = await _login(client, "sari@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Stocks9"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "BUY", "lots": 2,
            "price_per_share": 6900, "fee": 0, "executed_at": "2026-07-08",
        },
        headers=auth,
    )
    assert r.status_code == 201

    r = await client.get("/securities/BBCA/position", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["held"] is True

    p = body["positions"][0]
    assert p["portfolio_name"] == "Stocks9"
    assert p["lots"] == 2
    assert p["avg_cost_per_share"] == 6900.0
    assert p["cost_basis"] == 1_380_000
    assert p["market_value"] == 200 * 7000  # quote 7000
    assert p["unrealized_pnl"] == 20_000
    assert p["pct_of_portfolio"] == 100.0  # only holding in the portfolio

    # buy markers land on the right dates
    assert [(t["executed_at"], t["type"], t["lots"]) for t in body["transactions"]] == [
        ("2026-07-08", "BUY", 2)
    ]


async def test_holdings_fall_back_to_last_close(client):
    # AAAA has price history (seeded by the performance test) but no
    # latest_quotes row: the holdings table must price it at the last
    # stored close instead of showing a dash
    auth = await _login(client, "ujang@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "CloseFallback"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "AAAA", "type": "BUY", "lots": 1,
            "price_per_share": 1000, "fee": 0, "executed_at": "2026-06-02",
        },
        headers=auth,
    )
    assert r.status_code == 201

    h = (await client.get(f"/portfolios/{pid}/holdings", headers=auth)).json()
    row = h["holdings"][0]
    assert row["last_price"] == 1090  # AAAA's final synthetic close
    assert row["as_of"] is None  # not a quote…
    assert row["last_close_date"] == "2026-06-12"  # …but a dated close
    assert row["market_value"] == 100 * 1090
    assert h["totals"]["market_value"] == 109_000


async def test_position_absent_for_non_holder(client):
    auth = await _login(client, "tomi@example.com")
    r = await client.get("/securities/BBCA/position", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["held"] is False
    assert body["positions"] == []
    assert body["transactions"] == []
