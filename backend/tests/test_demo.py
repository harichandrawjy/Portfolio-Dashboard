"""Per-visitor demo accounts: minting, isolation, purging, and the guards.

The endpoint writes rows without authentication, so the rate limit and the
purge are not conveniences — they are the reason it is safe to expose. Both
are tested here alongside the happy path.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.demo import (
    DEMO_EMAIL_DOMAIN,
    TEMPLATE_EMAIL,
    TEMPLATE_PORTFOLIO_NAME,
    UNUSABLE_PASSWORD_HASH,
    purge_expired_demo_users,
)
from app.models import CashFlow, Portfolio, Security, Transaction, User
from app.ratelimit import SlidingWindowLimiter, client_key
from app.routers.auth import demo_limiter

pytestmark = pytest.mark.asyncio(loop_scope="session")

TEMPLATE_PORTFOLIO = TEMPLATE_PORTFOLIO_NAME


@pytest.fixture(autouse=True)
def _fresh_limiter():
    """Each test gets the full budget; otherwise order decides who gets 429."""
    demo_limiter.reset()
    yield
    demo_limiter.reset()


@pytest_asyncio.fixture(loop_scope="session")
async def template():
    """The seeded template account, built the way seed_demo builds it.

    Also clears demo accounts either side of the test. The test database is
    session-scoped, so without this a visitor minted by an earlier test is
    still around and "the demo user" stops identifying anything in
    particular — which silently turned the purge assertions into statements
    about whichever row happened to come back first.
    """
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(delete(User).where(User.is_demo.is_(True)))
            existing = await session.scalar(
                select(User).where(User.email == TEMPLATE_EMAIL)
            )
            if existing is not None:
                await session.execute(delete(User).where(User.id == existing.id))

            user = User(
                email=TEMPLATE_EMAIL,
                password_hash=UNUSABLE_PASSWORD_HASH,
                display_name="Demo",
            )
            session.add(user)
            await session.flush()

            portfolio = Portfolio(
                user_id=user.id,
                name=TEMPLATE_PORTFOLIO,
                description="Seeded demo",
            )
            session.add(portfolio)
            await session.flush()

            bbca = await session.scalar(select(Security).where(Security.ticker == "BBCA"))
            session.add(
                CashFlow(
                    portfolio_id=portfolio.id,
                    type="DEPOSIT",
                    amount=100_000_000,
                    occurred_at=date(2026, 1, 1),
                    note="opening deposit",
                )
            )
            session.add_all(
                Transaction(
                    portfolio_id=portfolio.id,
                    security_id=bbca.id,
                    type="BUY",
                    shares=shares,
                    price_per_share=7000,
                    fee=1000,
                    executed_at=date(2026, 7, 17),
                    note="demo seed",
                )
                for shares in (100, 200)
            )
    yield
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(delete(User).where(User.is_demo.is_(True)))
            await session.execute(delete(User).where(User.email == TEMPLATE_EMAIL))


async def _demo_count() -> int:
    async with SessionLocal() as session:
        return await session.scalar(
            select(func.count()).select_from(User).where(User.is_demo.is_(True))
        )


async def _age_demo_user(*, hours: int) -> None:
    """Backdate every demo account so the purge considers it stale.

    Backdating all of them rather than one: `created_at` carries a server
    default, so two accounts minted in the same test are microseconds apart
    and "the oldest one" is not a stable way to name the one you meant.
    """
    async with SessionLocal() as session:
        async with session.begin():
            demos = (
                await session.scalars(select(User).where(User.is_demo.is_(True)))
            ).all()
            for demo in demos:
                demo.created_at = datetime.now(timezone.utc) - timedelta(hours=hours)


async def test_mints_a_private_clone_of_the_template(client, template):
    r = await client.post("/auth/demo")
    assert r.status_code == 201
    token = r.json()["access_token"]
    assert r.json()["token_type"] == "bearer"

    auth = {"Authorization": f"Bearer {token}"}
    me = await client.get("/me", headers=auth)
    assert me.status_code == 200
    # A throwaway identity on a domain that can never be registered for real.
    assert me.json()["email"].endswith(f"@{DEMO_EMAIL_DOMAIN}")

    portfolios = await client.get("/portfolios", headers=auth)
    assert portfolios.status_code == 200
    assert [p["name"] for p in portfolios.json()] == [TEMPLATE_PORTFOLIO]

    pid = portfolios.json()[0]["id"]
    txns = await client.get(f"/portfolios/{pid}/transactions", headers=auth)
    # Paginated envelope, not a bare list.
    assert txns.json()["total"] == 2
    assert {t["lots"] for t in txns.json()["items"]} == {1, 2}

    # The cash ledger came across too, so the clone can actually be traded in
    # — a copy with transactions but no deposit would fail every buy.
    cash = await client.get(f"/portfolios/{pid}/cash", headers=auth)
    assert cash.json()["tracked"] is True
    assert cash.json()["balance"] > 0


async def test_clones_the_named_portfolio_not_merely_the_first(client, template):
    """A template account owning a second portfolio must not confuse the clone.

    Selecting "the template's oldest portfolio" passes every test where the
    account owns exactly one, and hands visitors the wrong one the moment
    somebody creates another while signed in as the demo — which is precisely
    what a real development database looks like.
    """
    async with SessionLocal() as session:
        async with session.begin():
            owner = await session.scalar(
                select(User).where(User.email == TEMPLATE_EMAIL)
            )
            # Backdated so it sorts FIRST by created_at — the exact condition
            # that made the original implementation pick it.
            session.add(
                Portfolio(
                    user_id=owner.id,
                    name="Some Other Portfolio",
                    description="not the demo",
                    created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                )
            )

    token = (await client.post("/auth/demo")).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    names = [p["name"] for p in (await client.get("/portfolios", headers=auth)).json()]
    assert names == [TEMPLATE_PORTFOLIO]


async def test_two_visitors_cannot_see_or_wreck_each_other(client, template):
    first = (await client.post("/auth/demo")).json()["access_token"]
    second = (await client.post("/auth/demo")).json()["access_token"]
    assert first != second

    auth_a = {"Authorization": f"Bearer {first}"}
    auth_b = {"Authorization": f"Bearer {second}"}

    a_pid = (await client.get("/portfolios", headers=auth_a)).json()[0]["id"]
    b_pid = (await client.get("/portfolios", headers=auth_b)).json()[0]["id"]
    assert a_pid != b_pid

    # The whole point of the change: one visitor deleting everything leaves
    # the next visitor's copy untouched.
    assert (
        await client.delete(f"/portfolios/{a_pid}", headers=auth_a)
    ).status_code == 204
    assert (await client.get("/portfolios", headers=auth_a)).json() == []
    assert len((await client.get("/portfolios", headers=auth_b)).json()) == 1

    # And it never reaches across to the template either.
    async with SessionLocal() as session:
        still_there = await session.scalar(
            select(func.count())
            .select_from(Portfolio)
            .join(User, User.id == Portfolio.user_id)
            .where(User.email == TEMPLATE_EMAIL)
        )
    assert still_there == 1


async def test_template_account_cannot_be_signed_into(client, template):
    """The password published in the README must not work any more."""
    r = await client.post(
        "/auth/login", json={"email": TEMPLATE_EMAIL, "password": "arus-demo-123"}
    )
    assert r.status_code == 401
    # Not a crash on the malformed hash — a plain failed login.
    assert "Incorrect" in r.json()["detail"]


async def test_unseeded_database_reports_unavailable(client):
    """No template (seed_demo never ran) is an operator problem, not a 500."""
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(delete(User).where(User.email == TEMPLATE_EMAIL))
    r = await client.post("/auth/demo")
    assert r.status_code == 503


async def test_rate_limit_rejects_a_flood(client, template):
    # The limiter's budget is 5/hour; the sixth call from one caller fails.
    codes = [(await client.post("/auth/demo")).status_code for _ in range(6)]
    assert codes[:5] == [201] * 5
    assert codes[5] == 429


async def test_purge_deletes_stale_demos_and_spares_everyone_else(client, template):
    await client.post("/auth/demo")
    r = await client.post(
        "/auth/register",
        json={"email": "real-person@example.com", "password": "not-a-demo-1"},
    )
    assert r.status_code == 201

    assert await _demo_count() == 1
    # Fresh demos survive.
    assert await purge_expired_demo_users(ttl=timedelta(hours=24)) == 0
    assert await _demo_count() == 1

    # Age it past the cutoff rather than sleeping for a day.
    await _age_demo_user(hours=48)

    assert await purge_expired_demo_users(ttl=timedelta(hours=24)) == 1
    assert await _demo_count() == 0

    # The registered account is untouched, and so is the template.
    async with SessionLocal() as session:
        assert await session.scalar(
            select(User).where(User.email == "real-person@example.com")
        )
        assert await session.scalar(select(User).where(User.email == TEMPLATE_EMAIL))


async def test_purge_takes_the_whole_tree_with_it(client, template):
    token = (await client.post("/auth/demo")).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    pid = (await client.get("/portfolios", headers=auth)).json()[0]["id"]

    await _age_demo_user(hours=72)
    await purge_expired_demo_users(ttl=timedelta(hours=24))

    # Cascades, not orphans: nothing should be left pointing at a dead user.
    async with SessionLocal() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(Portfolio).where(Portfolio.id == pid)
            )
        ) == 0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.portfolio_id == pid)
            )
        ) == 0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(CashFlow)
                .where(CashFlow.portfolio_id == pid)
            )
        ) == 0


# The limiter's own unit tests live in test_ratelimit.py — they are synchronous
# and this module's asyncio mark applies to everything in the file.
