"""Per-visitor demo accounts.

The demo used to be one shared, mutable account whose credentials were
compiled into the JS bundle. Anyone could sign in and delete the portfolio, so
what a visitor saw depended on what the previous visitor had done to it — and
keeping it presentable meant re-seeding on a cron.

Each visitor now gets a private clone. What makes that affordable is that the
expensive half of the demo is already global: `securities`, `price_history`,
`latest_quotes` and `fundamentals` are shared by every user, so minting a
visitor costs one user row, one portfolio, one cash flow and a dozen
transactions — roughly sixteen rows, no network, no price backfill.

The clone COPIES the template's rows rather than replaying `seed_demo`'s
SCRIPT. Transactions already carry `price_per_share`, so copying needs no
price lookups, does not depend on a bar existing near some target date, and
leaves exactly one implementation of what the demo portfolio contains. Replay
would be a second copy of those rules, free to drift from the first.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import CashFlow, Portfolio, Transaction, User

# The account `seed_demo` builds. Never signed into any more — it is the thing
# clones are cut from, and its password is deliberately unusable (below).
TEMPLATE_EMAIL = "demo@arus.id"

# The portfolio cloned for each visitor, matched BY NAME.
#
# Not "the template account's oldest portfolio", which was the first attempt
# and is wrong the moment that account owns more than one — a dev database
# where somebody once clicked "new portfolio" while signed in as the demo
# hands every visitor a copy of whichever one happened to be created first.
# The name is what `seed_demo` writes and what it checks for on re-runs, so
# it is the only stable handle on the intended portfolio.
TEMPLATE_PORTFOLIO_NAME = "Blue Chips (demo)"

# Addresses for minted visitors.
#
# NOT an RFC 2606 reserved name — `.invalid` was the obvious first choice and
# it fails: `UserOut.email` is a pydantic `EmailStr`, and email-validator
# rejects the special-use TLDs (invalid, local, localhost, test, ...) outright.
# The response model would then refuse to serialise the very user it had just
# created, so GET /me — which the frontend calls immediately after sign-in —
# would 500 for every demo visitor.
#
# A subdomain of the project's own name validates cleanly, and the uuid in the
# local part makes a collision with a real registration a non-event.
DEMO_EMAIL_DOMAIN = "demo.arus.id"

# A hash no password can match. `verify_password` runs bcrypt.checkpw, which
# raises ValueError on a malformed hash and is caught there and reported as a
# failed login — so this closes the credential path without a special case in
# the login handler.
#
# It also matters that it is cheap. Hashing a throwaway password properly
# would cost the ~100 ms bcrypt is designed to cost, on an UNAUTHENTICATED
# endpoint, on a 1/8-OCPU box: an invitation to pin the CPU by clicking a
# button in a loop. Nobody logs into these accounts; the endpoint hands back a
# token directly.
UNUSABLE_PASSWORD_HASH = "!demo-no-login"

# How long a minted demo survives the purge. Long enough that leaving a tab
# open over lunch does not lose the portfolio, short enough that the table
# does not carry a year of visitors.
DEMO_TTL = timedelta(hours=24)


class DemoUnavailable(RuntimeError):
    """No template to clone — `seed_demo` has not run on this database."""


async def _template_portfolio(session: AsyncSession) -> Portfolio | None:
    """The portfolio every demo visitor is given a copy of."""
    return await session.scalar(
        select(Portfolio)
        .join(User, User.id == Portfolio.user_id)
        .where(
            User.email == TEMPLATE_EMAIL,
            Portfolio.name == TEMPLATE_PORTFOLIO_NAME,
        )
        .limit(1)
    )


async def mint_demo_user(session: AsyncSession) -> User:
    """Create a throwaway user owning a private copy of the demo portfolio.

    Does NOT commit — the caller owns the transaction, so a failure partway
    through leaves no half-built visitor behind.
    """
    template = await _template_portfolio(session)
    if template is None:
        raise DemoUnavailable(
            "No demo template on this database; run `python -m app.seed_demo`."
        )

    user = User(
        email=f"demo-{uuid.uuid4().hex}@{DEMO_EMAIL_DOMAIN}",
        password_hash=UNUSABLE_PASSWORD_HASH,
        display_name="Demo",
        is_demo=True,
    )
    session.add(user)
    await session.flush()  # need user.id for the portfolio

    portfolio = Portfolio(
        user_id=user.id,
        name=template.name,
        description=template.description,
    )
    session.add(portfolio)
    await session.flush()  # need portfolio.id for the children

    # Read the template's ledger and re-add it under the new portfolio. A
    # dozen-odd rows through the ORM rather than INSERT..SELECT: the row count
    # is fixed and tiny, and the explicit field list is what makes it obvious
    # at review time that `id`, `portfolio_id` and `created_at` are the only
    # things deliberately NOT carried over.
    # `.all()` before adding: mutating the session while a result cursor from
    # it is still being consumed is asking for trouble. The row counts are
    # tiny, so materialising costs nothing.
    flows = (
        await session.scalars(
            select(CashFlow).where(CashFlow.portfolio_id == template.id)
        )
    ).all()
    session.add_all(
        CashFlow(
            portfolio_id=portfolio.id,
            type=flow.type,
            amount=flow.amount,
            occurred_at=flow.occurred_at,
            note=flow.note,
        )
        for flow in flows
    )

    txns = (
        await session.scalars(
            select(Transaction).where(Transaction.portfolio_id == template.id)
        )
    ).all()
    session.add_all(
        Transaction(
            portfolio_id=portfolio.id,
            security_id=txn.security_id,
            type=txn.type,
            shares=txn.shares,
            price_per_share=txn.price_per_share,
            fee=txn.fee,
            executed_at=txn.executed_at,
            note=txn.note,
        )
        for txn in txns
    )

    return user


async def purge_expired_demo_users(ttl: timedelta = DEMO_TTL) -> int:
    """Delete demo accounts older than `ttl`; returns how many went.

    Portfolios cascade from users and transactions/cash flows cascade from
    portfolios (schema.sql, migration 0004), so this one statement takes the
    whole tree with it.

    Scoped by `is_demo` and not by address: a registered user is never
    eligible no matter what they called themselves.
    """
    cutoff = datetime.now(timezone.utc) - ttl
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                delete(User).where(User.is_demo.is_(True), User.created_at < cutoff)
            )
    return result.rowcount or 0
