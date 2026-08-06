"""Portfolio cash ledger: derived balance, buy/withdraw enforcement.

The ledger is opt-in: a portfolio with no cash flows keeps the original
behavior (buys never blocked). The first deposit turns tracking on.
All numbers below are small and checkable by eye.
"""

from datetime import date

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


async def _buy(client, auth, pid, lots, price, fee=0, executed_at="2026-07-01"):
    return await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "BUY", "lots": lots,
            "price_per_share": price, "fee": fee, "executed_at": executed_at,
        },
        headers=auth,
    )


async def test_unfunded_portfolio_cannot_buy(client):
    auth = await _login(client, "wawan@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "NoLedger"}, headers=auth)
    ).json()["id"]

    r = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert r.json() == {
        "balance": 0,
        "tracked": False,
        "flows": [],
        "uncounted_trades": 0,
        "first_flow_date": None,
    }

    # nothing deposited -> a buy has no cash to spend
    r = await _buy(client, auth, pid, 10, 6000, fee=5000)
    assert r.status_code == 422
    assert "Insufficient cash" in r.json()["detail"]

    # deposit, and the same buy goes through
    await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 10_000_000, "occurred_at": "2026-06-01"},
        headers=auth,
    )
    assert (await _buy(client, auth, pid, 10, 6000, fee=5000)).status_code == 201


async def test_trades_before_first_deposit_do_not_count(client):
    """Funding a portfolio that already has history must not have its new
    deposit drained by those older trades."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Portfolio, Security, Transaction, User

    auth = await _login(client, "arif@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "LateLedger"}, headers=auth)
    ).json()["id"]

    # Insert the pre-funding trade directly: the API would (correctly) now
    # reject an unfunded buy, but portfolios imported from elsewhere can
    # legitimately carry history that predates the cash ledger.
    async with SessionLocal() as session:
        async with session.begin():
            sec_id = await session.scalar(
                select(Security.id).where(Security.ticker == "BBCA")
            )
            session.add(
                Transaction(
                    portfolio_id=pid, security_id=sec_id, type="BUY",
                    shares=100, price_per_share=6000, fee=0,
                    executed_at=date(2026, 7, 1),
                )
            )

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


async def test_trades_before_the_first_flow_are_reported_as_uncounted(client):
    """A trade dated before the funding never reduces the balance, so the
    portfolio reports cash it has already spent. The API no longer lets one be
    created (see test_buy_cannot_predate_the_first_cash_flow), but imported
    history can still carry them, so the summary has to say how many it
    skipped or the number is silently wrong."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Security, Transaction

    auth = await _login(client, "eka@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "Backdated"}, headers=auth)
    ).json()["id"]

    await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 10_000_000, "occurred_at": "2026-08-01"},
        headers=auth,
    )

    # Inserted directly: this is what an imported portfolio looks like. The
    # API rejects the same thing, which is the point of the sibling test.
    async with SessionLocal() as session:
        async with session.begin():
            sec_id = await session.scalar(
                select(Security.id).where(Security.ticker == "BBCA")
            )
            session.add(
                Transaction(
                    portfolio_id=pid, security_id=sec_id, type="BUY",
                    shares=1_000, price_per_share=6_000, fee=0,
                    executed_at=date(2026, 7, 15),
                )
            )

    cash = (await client.get(f"/portfolios/{pid}/cash", headers=auth)).json()
    assert cash["balance"] == 10_000_000  # the backdated buy did not spend it
    assert cash["uncounted_trades"] == 1
    assert cash["first_flow_date"] == "2026-08-01"

    # a trade on the funding date onwards does count, and is not flagged
    assert (
        await _buy(client, auth, pid, 1, 6_000, executed_at="2026-08-02")
    ).status_code == 201
    cash = (await client.get(f"/portfolios/{pid}/cash", headers=auth)).json()
    assert cash["balance"] == 10_000_000 - 600_000
    assert cash["uncounted_trades"] == 1


async def test_buy_cannot_predate_the_first_cash_flow(client):
    """The hole this closes: a buy dated before the funding is excluded from
    the derived balance, so its cost is never subtracted and the guards — which
    use that same balance — cannot see the overspend. Both the create and the
    edit path have to refuse the date, because on the create path the buy was
    genuinely affordable at the moment it was checked."""
    auth = await _login(client, "fajar@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "NoFreeLunch"}, headers=auth)
    ).json()["id"]

    await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 94_000_000, "occurred_at": "2026-08-01"},
        headers=auth,
    )

    # CREATE: affordable against the 94jt balance, but dated before it existed.
    # This used to be accepted and left the full deposit still spendable.
    r = await _buy(client, auth, pid, 150, 5_600, fee=12_600, executed_at="2026-03-04")
    assert r.status_code == 422
    assert "before the first cash flow" in r.json()["detail"]
    assert "2026-08-01" in r.json()["detail"]

    cash = (await client.get(f"/portfolios/{pid}/cash", headers=auth)).json()
    assert cash["balance"] == 94_000_000
    assert cash["uncounted_trades"] == 0

    # EDIT: record it legitimately, then try to move it behind the funding.
    r = await _buy(client, auth, pid, 150, 5_600, fee=12_600, executed_at="2026-08-02")
    assert r.status_code == 201
    txn_id = r.json()["id"]
    spent = 150 * 100 * 5_600 + 12_600

    r = await client.patch(
        f"/portfolios/{pid}/transactions/{txn_id}",
        json={
            "ticker": "BBCA", "type": "BUY", "lots": 150,
            "price_per_share": 5_600, "fee": 12_600, "executed_at": "2026-03-04",
        },
        headers=auth,
    )
    assert r.status_code == 422
    assert "before the first cash flow" in r.json()["detail"]

    # the trade kept its original date, and the cost is still accounted for
    cash = (await client.get(f"/portfolios/{pid}/cash", headers=auth)).json()
    assert cash["balance"] == 94_000_000 - spent
    assert cash["uncounted_trades"] == 0

    # moving it to a date on or after the funding is still allowed
    r = await client.patch(
        f"/portfolios/{pid}/transactions/{txn_id}",
        json={
            "ticker": "BBCA", "type": "BUY", "lots": 150,
            "price_per_share": 5_600, "fee": 12_600, "executed_at": "2026-08-01",
        },
        headers=auth,
    )
    assert r.status_code == 200


async def test_sell_may_still_predate_the_first_cash_flow(client):
    """Only BUY is restricted. A sell releases cash rather than spending it,
    and blocking it would strand portfolios whose imported history already
    sits behind the ledger's start."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Security, Transaction

    auth = await _login(client, "gita@example.com")
    pid = (
        await client.post("/portfolios", json={"name": "OldHistory"}, headers=auth)
    ).json()["id"]

    # imported holding that predates the ledger
    async with SessionLocal() as session:
        async with session.begin():
            sec_id = await session.scalar(
                select(Security.id).where(Security.ticker == "BBCA")
            )
            session.add(
                Transaction(
                    portfolio_id=pid, security_id=sec_id, type="BUY",
                    shares=1_000, price_per_share=6_000, fee=0,
                    executed_at=date(2026, 6, 1),
                )
            )

    await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": 1_000_000, "occurred_at": "2026-08-01"},
        headers=auth,
    )

    r = await client.post(
        f"/portfolios/{pid}/transactions",
        json={
            "ticker": "BBCA", "type": "SELL", "lots": 5,
            "price_per_share": 6_500, "fee": 0, "executed_at": "2026-07-01",
        },
        headers=auth,
    )
    assert r.status_code == 201


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
    assert r.json() == {
        "balance": 0,
        "tracked": False,
        "flows": [],
        "uncounted_trades": 0,
        "first_flow_date": None,
    }


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
