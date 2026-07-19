"""Portfolio cash ledger: derived balance, buy/withdraw enforcement.

The ledger is opt-in: a portfolio with no cash flows keeps the original
behavior (buys never blocked). The first deposit turns tracking on.
All numbers below are small and checkable by eye.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _login(client, email):
    await client.post(
        "/auth/register", json={"email": email, "password": "password-123"}
    )
    r = await client.post(
        "/auth/login", json={"email": email, "password": "password-123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _buy(client, auth, pid, lots, price, fee=0):
    return await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "BUY", "lots": lots,
            "price_per_share": price, "fee": fee, "executed_at": "2026-07-01",
        },
        headers=auth,
    )


async def test_untracked_portfolio_never_blocks_buys(client):
    auth = await _login(client, "wawan@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "NoLedger"}, headers=auth)
    ).json()["id"]

    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json() == {"balance": 0, "tracked": False, "flows": []}

    # no deposits ever -> buys work exactly as before the ledger existed
    assert (await _buy(client, auth, pid, 10, 6000, fee=5000)).status_code == 201

    # and the untracked balance stays 0 (trades don't apply pre-ledger)
    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json()["balance"] == 0


async def test_trades_before_first_deposit_do_not_count(client):
    auth = await _login(client, "arif@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "LateLedger"}, headers=auth)
    ).json()["id"]

    # trade first (2026-07-01), opt into cash later (2026-07-05):
    # the old buy must not drag the fresh deposit negative
    assert (await _buy(client, auth, pid, 1, 6000)).status_code == 201
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 500_000, "occurred_at": "2026-07-05"},
        headers=auth,
    )
    assert r.json()["balance"] == 500_000

    # so the full fresh deposit is withdrawable
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "WITHDRAW", "amount": 500_000},
        headers=auth,
    )
    assert r.status_code == 201
    assert r.json()["balance"] == 0


async def test_cash_ledger_enforces_balance(client):
    auth = await _login(client, "xena@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Ledger"}, headers=auth)
    ).json()["id"]

    # deposit 1_000_000 -> tracking on
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 1_000_000, "occurred_at": "2026-06-01"},
        headers=auth,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["balance"] == 1_000_000 and body["tracked"] is True
    assert len(body["flows"]) == 1

    # buy 1 lot @6000 + 500 fee = 600_500 -> ok, balance 399_500
    assert (await _buy(client, auth, pid, 1, 6000, fee=500)).status_code == 201
    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json()["balance"] == 399_500

    # a second identical buy exceeds the remaining cash -> 422
    r = await _buy(client, auth, pid, 1, 6000, fee=500)
    assert r.status_code == 422
    assert "Insufficient cash" in r.json()["detail"]

    # selling 1 lot @6100 - 500 fee credits 609_500 -> balance 1_009_000
    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 1,
            "price_per_share": 6100, "fee": 500, "executed_at": "2026-07-02",
        },
        headers=auth,
    )
    assert r.status_code == 201
    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json()["balance"] == 1_009_000

    # withdrawing more than the balance is rejected; exact balance is fine
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "WITHDRAW", "amount": 2_000_000},
        headers=auth,
    )
    assert r.status_code == 422
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "WITHDRAW", "amount": 1_000_000},
        headers=auth,
    )
    assert r.status_code == 201
    assert r.json()["balance"] == 9_000

    # holdings totals surface the ledger
    r = await client.get(f"/portfolios/{pid}/holdings", headers=auth)
    totals = r.json()["totals"]
    assert totals["cash_balance"] == 9_000 and totals["cash_tracked"] is True


async def test_delete_cash_flow_with_balance_guard(client):
    auth = await _login(client, "bela@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "CashDel"}, headers=auth)
    ).json()["id"]

    # two deposits: the big one funds a buy, the small one keeps the
    # ledger alive when we try to delete the big one
    dep = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 600_000, "occurred_at": "2026-06-01"},
        headers=auth,
    )
    dep_id = dep.json()["flows"][0]["id"]
    await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 100_000, "occurred_at": "2026-06-02"},
        headers=auth,
    )

    # spend most of it on a buy (1 lot @6000 + 500 fee = 600_500)
    assert (await _buy(client, auth, pid, 1, 6000, fee=500)).status_code == 201

    # deleting the big deposit would leave 100_000 - 600_500 < 0 -> refused
    r = await client.delete(f"/portfolios/{pid}/cash/{dep_id}", headers=auth)
    assert r.status_code == 422
    assert "balance" in r.json()["detail"]
    # and nothing changed
    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json()["balance"] == 99_500

    # a withdrawal entry can always be deleted (balance only goes up)
    w = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "WITHDRAW", "amount": 50_000},
        headers=auth,
    )
    w_id = next(f["id"] for f in w.json()["flows"] if f["type"] == "WITHDRAW")
    r = await client.delete(f"/portfolios/{pid}/cash/{w_id}", headers=auth)
    assert r.status_code == 204
    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json()["balance"] == 99_500

    # unknown flow -> 404
    r = await client.delete(
        f"/portfolios/{pid}/cash/00000000-0000-0000-0000-000000000000",
        headers=auth,
    )
    assert r.status_code == 404


async def test_deleting_the_only_flow_opts_out_of_tracking(client):
    auth = await _login(client, "cindy@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "OptOut"}, headers=auth)
    ).json()["id"]
    dep = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 100_000},
        headers=auth,
    )
    dep_id = dep.json()["flows"][0]["id"]
    assert dep.json()["tracked"] is True

    # removing the last flow is the supported way to turn the ledger off
    r = await client.delete(f"/portfolios/{pid}/cash/{dep_id}", headers=auth)
    assert r.status_code == 204
    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json() == {"balance": 0, "tracked": False, "flows": []}


async def test_cash_validation(client):
    auth = await _login(client, "yani@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "CashVal"}, headers=auth)
    ).json()["id"]

    # future-dated and non-positive amounts are rejected
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 1000, "occurred_at": "2030-01-01"},
        headers=auth,
    )
    assert r.status_code == 422
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 0},
        headers=auth,
    )
    assert r.status_code == 422

    # another user cannot touch this portfolio's cash
    auth_b = await _login(client, "zaki@example.com")
    r = await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 1000},
        headers=auth_b,
    )
    assert r.status_code == 404
