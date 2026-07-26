"""Allocation math + concentration flags, and local universe search.

Allocation fixture (quotes chosen for eyeball-checkable weights):

  CCCC  sector Keuangan  1 lot, quote 10_000  -> mv 1_000_000  (50%)
  DDDD  sector Keuangan  1 lot, quote  5_000  -> mv   500_000  (25%)
  EEEE  sector Energi    1 lot, quote  5_000  -> mv   500_000  (25%)
  FFFF  sector Energi    1 lot, NO price      -> unpriced, excluded

  total priced market value: 2_000_000
  flags expected:
    - CCCC at 50%      > 30% stock threshold
    - Keuangan at 75%  > 50% sector threshold
  (Energi at 25% and DDDD/EEEE at 25% must NOT be flagged.)
"""

import pytest

from tests.helpers import fund

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_allocation_market():
    from datetime import datetime, timezone

    from app.db import SessionLocal
    from app.models import LatestQuote, Security

    as_of = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)
    async with SessionLocal() as session:
        async with session.begin():
            specs = [
                ("CCCC", "Keuangan", 10_000),
                ("DDDD", "Keuangan", 5_000),
                ("EEEE", "Energi", 5_000),
                ("FFFF", "Energi", None),  # held but unpriced
            ]
            for ticker, sector, quote in specs:
                sec = Security(
                    ticker=ticker, yahoo_symbol=f"{ticker}.JK",
                    name=f"Synthetic {ticker} Tbk.", kind="stock", sector=sector,
                )
                session.add(sec)
                await session.flush()
                if quote is not None:
                    session.add(
                        LatestQuote(security_id=sec.id, price=quote, as_of=as_of)
                    )
            # an inactive stock: search must never return it
            session.add(
                Security(
                    ticker="GGGG", yahoo_symbol="GGGG.JK",
                    name="Delisted Zombie Tbk.", kind="stock",
                    sector="Energi", is_active=False,
                )
            )


async def _login(client, email):
    await client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    r = await client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_allocation_math_and_flags(client):
    await _seed_allocation_market()
    auth = await _login(client, "indra@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Alloc"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)

    for ticker in ("CCCC", "DDDD", "EEEE", "FFFF"):
        r = await client.post(
            f"/portfolios/{pid}/transactions",
            json={
                "ticker": ticker, "type": "BUY", "lots": 1,
                "price_per_share": 1000, "fee": 0, "executed_at": "2026-07-01",
            },
            headers=auth,
        )
        assert r.status_code == 201

    r = await client.get(f"/portfolios/{pid}/allocation", headers=auth)
    assert r.status_code == 200
    body = r.json()

    assert body["total_market_value"] == 2_000_000
    assert body["unpriced"] == ["FFFF"]

    # by_stock: sorted by market value desc, ties by ticker
    assert [(s["ticker"], s["market_value"], s["weight_pct"]) for s in body["by_stock"]] == [
        ("CCCC", 1_000_000, 50.0),
        ("DDDD", 500_000, 25.0),
        ("EEEE", 500_000, 25.0),
    ]

    # by_sector: Keuangan 1.5M (75%), Energi 0.5M (25%)
    assert [(s["sector"], s["market_value"], s["weight_pct"]) for s in body["by_sector"]] == [
        ("Keuangan", 1_500_000, 75.0),
        ("Energi", 500_000, 25.0),
    ]

    # exactly two flags: CCCC > 30%, Keuangan > 50%
    flags = {(f["type"], f.get("ticker") or f.get("sector")) for f in body["flags"]}
    assert flags == {
        ("stock_concentration", "CCCC"),
        ("sector_concentration", "Keuangan"),
    }
    for f in body["flags"]:
        if f["type"] == "stock_concentration":
            assert f["weight_pct"] == 50.0 and f["threshold_pct"] == 30.0
        else:
            assert f["weight_pct"] == 75.0 and f["threshold_pct"] == 50.0


async def test_allocation_empty_portfolio(client):
    auth = await _login(client, "joko@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Nothing"}, headers=auth)
    ).json()["id"]
    r = await client.get(f"/portfolios/{pid}/allocation", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["total_market_value"] == 0
    assert body["by_stock"] == [] and body["flags"] == []


async def test_search_ticker_prefix_and_name_substring(client):
    auth = await _login(client, "kiki@example.com")

    # prefix on ticker
    r = await client.get("/securities/search?q=bb", headers=auth)
    assert r.status_code == 200
    tickers = [s["ticker"] for s in r.json()]
    assert "BBCA" in tickers
    assert len(tickers) <= 10

    # substring on company name
    r = await client.get("/securities/search?q=central", headers=auth)
    assert "BBCA" in [s["ticker"] for s in r.json()]

    # ticker-prefix hits rank before name-substring hits
    r = await client.get("/securities/search?q=cc", headers=auth)
    assert r.json()[0]["ticker"] == "CCCC"


async def test_search_covers_tickers_without_price_history(client):
    auth = await _login(client, "lala@example.com")
    # TLKM is seeded with no price_history rows at all — must still appear,
    # with no last_price to pre-fill
    r = await client.get("/securities/search?q=telkom", headers=auth)
    tlkm = next(s for s in r.json() if s["ticker"] == "TLKM")
    assert tlkm["last_price"] is None


async def test_search_returns_last_price_for_entry_autofill(client):
    auth = await _login(client, "nana@example.com")
    # BBCA has a seeded quote of 7000 — search carries it for the
    # transaction form's price pre-fill
    r = await client.get("/securities/search?q=bbca", headers=auth)
    bbca = next(s for s in r.json() if s["ticker"] == "BBCA")
    assert bbca["last_price"] == 7000


async def test_ensure_prices_endpoint(client, monkeypatch):
    import app.routers.securities as securities_router

    calls: list[str] = []
    monkeypatch.setattr(securities_router, "enqueue_backfill", calls.append)

    auth = await _login(client, "opik@example.com")

    # BBCA already has price history -> ready, nothing enqueued
    r = await client.post("/securities/BBCA/ensure-prices", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert calls == []

    # TLKM has none -> backfill queued
    r = await client.post("/securities/TLKM/ensure-prices", headers=auth)
    assert r.json()["status"] == "queued"
    assert calls == ["TLKM"]

    # unknown ticker -> 404
    r = await client.post("/securities/XXXX/ensure-prices", headers=auth)
    assert r.status_code == 404


async def test_search_excludes_inactive_and_requires_auth(client):
    auth = await _login(client, "mimi@example.com")

    r = await client.get("/securities/search?q=gggg", headers=auth)
    assert r.json() == []  # delisted stock never surfaces

    r = await client.get("/securities/search?q=zombie", headers=auth)
    assert r.json() == []

    r = await client.get("/securities/search?q=bb")  # no token
    assert r.status_code == 401
