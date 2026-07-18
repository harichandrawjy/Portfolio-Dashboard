"""Fundamentals sync + the detail endpoint's nullable block.

Yahoo is mocked here (unit boundary is Ticker.info's dict); the live
coverage patchiness is exercised in the step's manual verification.
Seeds its own tickers (FNDA large-cap-ish, FNDB patchy small cap) so the
file is order-independent.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

_seeded = False


async def _seed_tickers():
    global _seeded
    if _seeded:
        return
    _seeded = True
    from app.db import SessionLocal
    from app.models import PriceHistory, Security

    async with SessionLocal() as session:
        async with session.begin():
            for ticker in ("FNDA", "FNDB"):
                sec = Security(
                    ticker=ticker, yahoo_symbol=f"{ticker}.JK",
                    name=f"Fundamental {ticker} Tbk.", kind="stock",
                )
                session.add(sec)
                await session.flush()
                session.add(PriceHistory(
                    security_id=sec.id, trade_date=date(2026, 7, 17), close=500,
                ))


async def _login(client, email):
    await client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    r = await client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_sync_stores_partial_and_empty_info(client, monkeypatch):
    await _seed_tickers()
    import app.sync.fundamentals as fund

    # FNDA: complete large-cap payload. FNDB: the patchy small-cap case —
    # Yahoo answered but knew almost nothing.
    payloads = {
        "FNDA.JK": {
            "marketCap": 795_623_632_666_624,
            "trailingPE": 13.7552,
            "trailingEps": 470.73,
            "dividendYield": 5.5,
            "bookValue": 2108.889,
        },
        "FNDB.JK": {"marketCap": 142_800_633_856},
    }
    monkeypatch.setattr(fund, "_fetch_info", lambda sym: payloads.get(sym, {}))

    result = await fund.sync_fundamentals(["FNDA", "FNDB"])
    assert result.synced == 2 and result.failed == []

    auth = await _login(client, "udin@example.com")

    r = await client.get("/securities/FNDA", headers=auth)
    f = r.json()["fundamentals"]
    assert f["market_cap"] == 795_623_632_666_624
    assert f["pe_ratio"] == pytest.approx(13.7552)
    assert f["eps"] == pytest.approx(470.73)
    assert f["dividend_yield_pct"] == pytest.approx(5.5)
    assert f["book_value"] == pytest.approx(2108.889)
    assert f["last_updated"] is not None

    r = await client.get("/securities/FNDB", headers=auth)
    f = r.json()["fundamentals"]
    # row exists (we asked), fields Yahoo didn't know are null
    assert f["market_cap"] == 142_800_633_856
    assert f["pe_ratio"] is None
    assert f["eps"] is None
    assert f["dividend_yield_pct"] is None
    assert f["book_value"] is None


async def test_detail_works_with_no_fundamentals_row(client):
    await _seed_tickers()
    auth = await _login(client, "vina@example.com")
    # BBCA has price history but no fundamentals row was ever written
    # (this file's sync only touched FNDA/FNDB)
    r = await client.get("/securities/BBCA", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["fundamentals"] is None
    # and the rest of the page's data is fully intact
    assert body["has_history"] is True
    assert body["last_close"] is not None


async def test_one_bad_ticker_does_not_kill_the_run(client, monkeypatch):
    await _seed_tickers()
    import app.sync.fundamentals as fund

    def explode_on_fndb(sym: str) -> dict:
        if sym == "FNDB.JK":
            raise RuntimeError("Yahoo tantrum")
        return {"marketCap": 1_000_000}

    monkeypatch.setattr(fund, "_fetch_info", explode_on_fndb)
    result = await fund.sync_fundamentals(["FNDA", "FNDB"])
    assert result.synced == 1
    assert result.failed == ["FNDB"]
