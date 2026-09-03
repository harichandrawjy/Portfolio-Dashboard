import pytest

from tests.helpers import fund, register_verified

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "password-123"


async def _login(client, email):
    """Register, verify and sign in. See helpers.register_verified."""
    return await register_verified(client, email, PASSWORD)


async def _buy(client, auth, pid, ticker, lots, price, fee=0, day="2026-07-01"):
    return await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": ticker, "type": "BUY", "lots": lots,
            "price_per_share": price, "fee": fee, "executed_at": day,
        },
        headers=auth,
    )


async def test_buy_sell_holdings_math(client):
    auth = await _login(client, "andi@example.com")
    r = await client.post(
        "/portfolios", json={"name": "Growth", "description": "long term"}, headers=auth
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    await fund(client, auth, pid)

    # buy 5 lots @ 6000
    r = await _buy(client, auth, pid, "BBCA", 5, 6000, day="2026-07-01")
    assert r.status_code == 201
    assert r.json()["shares"] == 500 and r.json()["lots"] == 5

    # buy 3 lots @ 6400
    r = await _buy(client, auth, pid, "BBCA", 3, 6400, day="2026-07-05")
    assert r.status_code == 201

    # sell 2 lots @ 6500
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 2,
            "price_per_share": 6500, "fee": 0, "executed_at": "2026-07-10",
        },
        headers=auth,
    )
    assert r.status_code == 201

    r = await client.get(f"/portfolios/{pid}/holdings", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert len(body["holdings"]) == 1
    h = body["holdings"][0]
    # 800 shares bought, 200 sold -> 600 shares = 6 lots
    assert h["shares"] == 600
    assert h["lots"] == 6
    # avg cost over buys only: (500*6000 + 300*6400) / 800 = 6150
    assert h["avg_cost_per_share"] == 6150.0
    assert h["cost_basis"] == 600 * 6150  # 3_690_000
    # 7000 either way: conftest seeds a 7000 bar and a 7000 quote.
    assert h["last_price"] == 7000
    assert h["market_value"] == 600 * 7000  # 4_200_000
    assert h["unrealized_pnl"] == 510_000
    assert h["unrealized_pnl_pct"] == pytest.approx(13.82, abs=0.01)
    # ...but the price came from the BAR, so there is no quote timestamp to
    # report. The seeded quote carries no trade_date, so it cannot be shown to
    # be newer than the last bar, and an unplaceable quote is not trusted —
    # the same rule Stock.tsx applies via `quote_trade_date != null && ...`.
    # A null here is the holdings table saying "priced at last close", which
    # is what the UI labels it. See test_quote_freshness for the rule itself.
    assert h["as_of"] is None
    assert h["last_close_date"] == "2026-07-17"

    totals = body["totals"]
    assert totals["cost_basis"] == 3_690_000
    assert totals["market_value"] == 4_200_000
    assert totals["unpriced_holdings"] == 0

    # realized: sold 200 sh @ 6500 with avg cost 6150 -> (6500-6150)*200 = +70_000
    assert h["realized_pnl"] == 70_000
    assert totals["realized_pnl"] == 70_000


async def test_fees_included_in_avg_cost(client):
    auth = await _login(client, "fee@example.com")
    r = await client.post("/portfolios", json={"name": "Fees"}, headers=auth)
    pid = r.json()["id"]
    await fund(client, auth, pid)
    # 1 lot @ 1000 with fee 5000: avg = (100*1000 + 5000) / 100 = 1050
    r = await _buy(client, auth, pid, "BBCA", 1, 1000, fee=5000)
    assert r.status_code == 201
    r = await client.get(f"/portfolios/{pid}/holdings", headers=auth)
    assert r.json()["holdings"][0]["avg_cost_per_share"] == 1050.0


async def test_oversell_rejected(client):
    auth = await _login(client, "budi2@example.com")
    r = await client.post("/portfolios", json={"name": "Trades"}, headers=auth)
    pid = r.json()["id"]
    await fund(client, auth, pid)

    # nothing held yet
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 1,
            "price_per_share": 6000, "fee": 0, "executed_at": "2026-07-01",
        },
        headers=auth,
    )
    assert r.status_code == 422

    # buy 2, try to sell 3
    assert (await _buy(client, auth, pid, "BBCA", 2, 6000)).status_code == 201
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 3,
            "price_per_share": 6000, "fee": 0, "executed_at": "2026-07-02",
        },
        headers=auth,
    )
    assert r.status_code == 422
    assert "only 2 held" in r.json()["detail"]


async def test_cross_user_isolation(client):
    auth_a = await _login(client, "alice@example.com")
    auth_b = await _login(client, "bob@example.com")

    r = await client.post("/portfolios", json={"name": "Private"}, headers=auth_a)
    pid = r.json()["id"]

    assert (await client.get(f"/portfolios/{pid}", headers=auth_b)).status_code == 404
    assert (
        await client.get(f"/portfolios/{pid}/holdings", headers=auth_b)
    ).status_code == 404
    r = await _buy(client, auth_b, pid, "BBCA", 1, 6000)
    assert r.status_code == 404
    assert (
        await client.delete(f"/portfolios/{pid}", headers=auth_b)
    ).status_code == 404

    # B's own list doesn't contain A's portfolio
    r = await client.get("/portfolios", headers=auth_b)
    assert pid not in [p["id"] for p in r.json()]


async def test_first_use_ticker_enqueues_backfill(client, monkeypatch):
    import app.routers.portfolios as portfolios_router

    calls: list[str] = []
    monkeypatch.setattr(portfolios_router, "enqueue_backfill", calls.append)

    auth = await _login(client, "citra@example.com")
    r = await client.post("/portfolios", json={"name": "Lazy"}, headers=auth)
    pid = r.json()["id"]
    await fund(client, auth, pid)

    # TLKM has no price history -> must enqueue
    r = await _buy(client, auth, pid, "TLKM", 1, 2600)
    assert r.status_code == 201
    assert calls == ["TLKM"]

    # BBCA already has history -> must NOT enqueue
    r = await _buy(client, auth, pid, "BBCA", 1, 6000)
    assert r.status_code == 201
    assert calls == ["TLKM"]


async def test_transaction_writes_nudge_the_ticker_quote(client, monkeypatch):
    """Add, edit and delete all changed what this portfolio holds, and a held
    ticker is exactly what `sync_quotes` scopes its 15-minute refresh to.
    Reported as a real bug: cancelling (deleting) a sell left the ticker's
    price and its today-candle stuck on a frozen quote until the next tick."""
    import app.routers.portfolios as portfolios_router

    calls: list[str] = []
    monkeypatch.setattr(portfolios_router, "enqueue_quote_refresh", calls.append)

    auth = await _login(client, "essa@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Watched"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)

    # BBCA already has history, so this is a quote nudge, not a backfill.
    r = await _buy(client, auth, pid, "BBCA", 1, 6000)
    assert r.status_code == 201
    txn_id = r.json()["id"]
    assert calls == ["BBCA"]

    r = await client.patch(
        f"/portfolios/{pid}/transactions/{txn_id}",
        json={
            "type": "BUY", "lots": 2, "price_per_share": 6000, "fee": 0,
            "executed_at": "2026-07-01", "note": None,
        },
        headers=auth,
    )
    assert r.status_code == 200
    assert calls == ["BBCA", "BBCA"]

    # The reported scenario: selling, then deleting that sell — "cancelling"
    # it — must nudge the quote again once the position is back.
    sell = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 1,
            "price_per_share": 6100, "fee": 0, "executed_at": "2026-07-02",
        },
        headers=auth,
    )
    assert sell.status_code == 201
    assert calls == ["BBCA", "BBCA", "BBCA"]

    r = await client.delete(
        f"/portfolios/{pid}/transactions/{sell.json()['id']}", headers=auth
    )
    assert r.status_code == 204
    assert calls == ["BBCA", "BBCA", "BBCA", "BBCA"]


async def test_edit_transaction(client):
    auth = await _login(client, "edit@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Editable"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)

    buy = await _buy(client, auth, pid, "BBCA", 5, 6000, day="2026-07-01")
    txn_id = buy.json()["id"]

    # edit lots and price
    r = await client.patch(
        f"/portfolios/{pid}/transactions/{txn_id}",
        json={
            "type": "BUY", "lots": 8, "price_per_share": 6100,
            "fee": 10000, "executed_at": "2026-07-02",
        },
        headers=auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["lots"] == 8 and body["shares"] == 800
    assert body["price_per_share"] == 6100 and body["fee"] == 10000
    assert body["executed_at"] == "2026-07-02"

    # holdings reflect the edit: 8 lots, avg = (800*6100 + 10000)/800 = 6112.5
    h = (await client.get(f"/portfolios/{pid}/holdings", headers=auth)).json()
    assert h["holdings"][0]["lots"] == 8
    assert h["holdings"][0]["avg_cost_per_share"] == 6112.5


async def test_edit_rejected_when_it_would_strand_sells(client):
    auth = await _login(client, "editguard@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "EditGuard"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid)

    buy = await _buy(client, auth, pid, "BBCA", 5, 6000)
    buy_id = buy.json()["id"]
    # sell 3 -> net 2
    await client.post(
        f"/portfolios/{pid}/transactions",
        json={"ticker": "BBCA", "type": "SELL", "lots": 3,
              "price_per_share": 6200, "fee": 0, "executed_at": "2026-07-05"},
        headers=auth,
    )

    # shrinking the buy to 2 lots would make net = 2 - 3 = -1 -> reject
    r = await client.patch(
        f"/portfolios/{pid}/transactions/{buy_id}",
        json={"type": "BUY", "lots": 2, "price_per_share": 6000,
              "fee": 0, "executed_at": "2026-07-01"},
        headers=auth,
    )
    assert r.status_code == 422
    assert "holdings" in r.json()["detail"]

    # unchanged: still 5 lots bought
    h = (await client.get(f"/portfolios/{pid}/holdings", headers=auth)).json()
    assert h["holdings"][0]["lots"] == 2  # 5 bought - 3 sold


async def test_edit_requires_ownership(client):
    auth_a = await _login(client, "editowner@example.com")
    auth_b = await _login(client, "editother@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Owned"}, headers=auth_a)
    ).json()["id"]
    await fund(client, auth_a, pid)
    txn_id = (await _buy(client, auth_a, pid, "BBCA", 1, 6000)).json()["id"]

    r = await client.patch(
        f"/portfolios/{pid}/transactions/{txn_id}",
        json={"type": "BUY", "lots": 2, "price_per_share": 6000,
              "fee": 0, "executed_at": "2026-07-01"},
        headers=auth_b,
    )
    assert r.status_code == 404


async def test_transaction_validation(client):
    auth = await _login(client, "dodi@example.com")
    r = await client.post("/portfolios", json={"name": "Val"}, headers=auth)
    pid = r.json()["id"]

    base = {"ticker": "BBCA", "type": "BUY", "price_per_share": 6000,
            "fee": 0, "executed_at": "2026-07-01"}

    for bad in (
        {**base, "lots": 0},                      # zero lots
        {**base, "lots": -1},                     # negative lots
        {**base, "lots": 1, "price_per_share": 0},  # free stock
        {**base, "lots": 1, "fee": -1},           # negative fee
    ):
        r = await client.post(
            f"/portfolios/{pid}/transactions", json=bad, headers=auth
        )
        assert r.status_code == 422, bad

    # unknown ticker and index both rejected
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={**base, "lots": 1, "ticker": "XXXX"}, headers=auth,
    )
    assert r.status_code == 422
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={**base, "lots": 1, "ticker": "IHSG"}, headers=auth,
    )
    assert r.status_code == 422

    # future date rejected
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={**base, "lots": 1, "executed_at": "2030-01-01"}, headers=auth,
    )
    assert r.status_code == 422


async def test_list_pagination_and_delete_integrity(client):
    auth = await _login(client, "eka@example.com")
    r = await client.post("/portfolios", json={"name": "Ledger"}, headers=auth)
    pid = r.json()["id"]
    await fund(client, auth, pid)

    buy = await _buy(client, auth, pid, "BBCA", 2, 6000, day="2026-07-01")
    sell = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 1,
            "price_per_share": 6200, "fee": 0, "executed_at": "2026-07-02",
        },
        headers=auth,
    )
    buy_id, sell_id = buy.json()["id"], sell.json()["id"]

    r = await client.get(
        f"/portfolios/{pid}/transactions?limit=1&offset=0", headers=auth
    )
    body = r.json()
    assert body["total"] == 2 and len(body["items"]) == 1
    assert body["items"][0]["id"] == sell_id  # newest executed_at first

    # deleting the only buy would strand the sell -> 422
    r = await client.delete(
        f"/portfolios/{pid}/transactions/{buy_id}", headers=auth
    )
    assert r.status_code == 422

    # delete sell, then buy — both fine, holdings empty
    assert (
        await client.delete(f"/portfolios/{pid}/transactions/{sell_id}", headers=auth)
    ).status_code == 204
    assert (
        await client.delete(f"/portfolios/{pid}/transactions/{buy_id}", headers=auth)
    ).status_code == 204
    r = await client.get(f"/portfolios/{pid}/holdings", headers=auth)
    assert r.json()["holdings"] == []


async def test_deleting_a_sell_that_funded_a_later_buy_is_refused(client):
    """Reported as a real bug: 100jt deposited, sold BBCA for 50jt and spent
    all 100jt (the leftover deposit plus that 50jt) buying TLKM, then deleted
    the old BBCA sell. Deleting it put the BBCA shares back — that is what
    deleting a sell always does — but nothing took the 50jt back out of
    TLKM, so the portfolio read as 150jt of stock funded by a 100jt deposit.
    Symmetric with the existing "deleting a buy must not orphan a sell"
    guard, just on the cash side instead of the share side."""
    auth = await _login(client, "delete-sell-overdraw@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Overdraft"}, headers=auth)
    ).json()["id"]
    await fund(client, auth, pid, 100_000_000)

    buy_bbca = await _buy(client, auth, pid, "BBCA", 100, 5_000)  # 50jt
    assert buy_bbca.status_code == 201
    sell_bbca = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 100,
            "price_per_share": 5_000, "fee": 0, "executed_at": "2026-07-01",
        },
        headers=auth,
    )
    assert sell_bbca.status_code == 201  # cash back to 100jt, BBCA at 0
    buy_tlkm = await _buy(client, auth, pid, "TLKM", 100, 10_000)  # 100jt
    assert buy_tlkm.status_code == 201  # cash to 0

    # Deleting the sell would restore BBCA (50jt) on top of the TLKM already
    # bought with its proceeds (100jt) — 150jt of stock on a 100jt deposit.
    r = await client.delete(
        f"/portfolios/{pid}/transactions/{sell_bbca.json()['id']}", headers=auth
    )
    assert r.status_code == 422
    assert "overdraw" in r.json()["detail"]

    # Nothing moved: the sell is still there, BBCA still at 0, cash still 0.
    holdings = (
        await client.get(f"/portfolios/{pid}/holdings", headers=auth)
    ).json()
    tickers = {h["ticker"] for h in holdings["holdings"]}
    assert tickers == {"TLKM"}
    assert holdings["totals"]["cash_balance"] == 0

    # Freeing the cash first makes the same delete legitimate.
    assert (
        await client.delete(
            f"/portfolios/{pid}/transactions/{buy_tlkm.json()['id']}", headers=auth
        )
    ).status_code == 204
    assert (
        await client.delete(
            f"/portfolios/{pid}/transactions/{sell_bbca.json()['id']}", headers=auth
        )
    ).status_code == 204
    holdings = (
        await client.get(f"/portfolios/{pid}/holdings", headers=auth)
    ).json()
    assert {h["ticker"] for h in holdings["holdings"]} == {"BBCA"}
    assert holdings["totals"]["cash_balance"] == 50_000_000
