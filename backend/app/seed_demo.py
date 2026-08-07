"""One-command demo seed:  python -m app.seed_demo

Creates a demo user with a realistic IDX portfolio spanning two years.
Transaction prices are the ACTUAL closes on their dates (taken from the
backfilled history), so the performance chart and P&L tell a true story.

Idempotent: a second run detects the demo portfolio and exits.
Requires: migrations applied, network access for the first run
(price backfills via yfinance; universe via IDX or the bundled CSV).
"""

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import func, or_, select

from app.db import SessionLocal
from app.models import CashFlow, Portfolio, PriceHistory, Security, Transaction, User
from app.demo import (
    TEMPLATE_EMAIL,
    TEMPLATE_PORTFOLIO_NAME,
    UNUSABLE_PASSWORD_HASH,
)
from app.sync.fundamentals import sync_fundamentals
from app.sync.prices import backfill_ticker, sync_quotes
from app.sync.universe import sync_universe

logger = logging.getLogger(__name__)

# The template every visitor's demo is cloned from (app/demo.py). It is no
# longer an account anyone signs into: its password is deliberately unusable,
# so the credentials that used to ship in the JS bundle — and are still in the
# README's history and in older builds — cannot be used to edit what visitors
# see. Nothing but POST /auth/demo reads this row.
DEMO_EMAIL = TEMPLATE_EMAIL
# Defined in app/demo.py, because that is what looks the portfolio up when
# cloning it for a visitor. One definition: if these two ever disagreed, the
# seed would build a portfolio the demo endpoint could not find, and the only
# symptom would be a 503 from a database that looks correctly seeded.
PORTFOLIO_NAME = TEMPLATE_PORTFOLIO_NAME

# (ticker, months_ago, type, lots) — a two-year story with buys and sells
SCRIPT: list[tuple[str, int, str, int]] = [
    ("BBCA", 24, "BUY", 20),
    ("TLKM", 24, "BUY", 30),
    ("ASII", 21, "BUY", 15),
    ("BMRI", 18, "BUY", 25),
    ("UNVR", 18, "BUY", 20),
    ("TLKM", 15, "SELL", 10),
    ("GOTO", 12, "BUY", 200),
    ("ANTM", 12, "BUY", 30),
    ("BBCA", 9, "BUY", 10),
    ("UNVR", 6, "SELL", 10),
    ("SIDO", 6, "BUY", 50),
    ("ANTM", 3, "BUY", 20),
    ("GOTO", 1, "SELL", 100),
]
TICKERS = sorted({t for t, *_ in SCRIPT})
# Stockbit-style retail fees: 0.15% on buys, 0.25% on sells
BUY_FEE_RATE = 0.0015
SELL_FEE_RATE = 0.0025


async def _has_bars(ident: str) -> bool:
    async with SessionLocal() as session:
        found = await session.scalar(
            select(PriceHistory.security_id)
            .join(Security, Security.id == PriceHistory.security_id)
            .where(
                or_(
                    Security.ticker == ident.upper(),
                    Security.yahoo_symbol == ident,
                )
            )
            .limit(1)
        )
        return found is not None


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    # 1. Universe must exist (IDX live, or the bundled CSV fallback)
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Security))
    if count == 0:
        print("Universe is empty — seeding the IDX ticker list…")
        await sync_universe()

    # 2. Already seeded?
    async with SessionLocal() as session:
        async with session.begin():
            user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
            if user is not None and user.password_hash != UNUSABLE_PASSWORD_HASH:
                # Upgrade path for databases seeded before per-visitor demos:
                # the template used to hold a real hash of a password printed
                # in the README, which still let anyone sign in and edit the
                # thing clones are cut from. Neuter it every run, so the fix
                # lands even when the portfolio itself is already in place and
                # the block below returns early.
                user.password_hash = UNUSABLE_PASSWORD_HASH
                print("Retired the old shared demo password on the template account.")

        if user is not None:
            existing = await session.scalar(
                select(Portfolio.id).where(
                    Portfolio.user_id == user.id,
                    Portfolio.name == PORTFOLIO_NAME,
                )
            )
            if existing is not None:
                print("Demo template already seeded — visitors get their own clone.")
                return

    # 3. Five years of daily bars for every demo ticker + the benchmark
    for ident in [*TICKERS, "^JKSE"]:
        if await _has_bars(ident):
            continue
        print(f"Backfilling {ident}…")
        result = await backfill_ticker(ident)
        if not result.resolved:
            raise SystemExit(f"Could not backfill {ident}; is the network up?")

    # 4. User, portfolio, and the scripted transactions at real closes
    today = date.today()
    async with SessionLocal() as session:
        async with session.begin():
            if user is None:
                user = User(
                    email=DEMO_EMAIL,
                    # Not a login. Visitors get a clone via POST /auth/demo;
                    # this row exists only to be copied from.
                    password_hash=UNUSABLE_PASSWORD_HASH,
                    display_name="Demo",
                )
                session.add(user)
                await session.flush()

            portfolio = Portfolio(
                user_id=user.id,
                name=PORTFOLIO_NAME,
                description="Seeded demo: IDX large caps traded over two years",
            )
            session.add(portfolio)
            await session.flush()

            # Opening deposit: the scripted buys cost ~Rp 86M and sells
            # return ~Rp 5M, leaving a realistic leftover cash balance.
            session.add(
                CashFlow(
                    portfolio_id=portfolio.id,
                    type="DEPOSIT",
                    amount=100_000_000,
                    occurred_at=today - timedelta(days=24 * 30 + 7),
                    note="opening deposit",
                )
            )

            for ticker, months_ago, txn_type, lots in SCRIPT:
                sec = await session.scalar(
                    select(Security).where(Security.ticker == ticker)
                )
                target = today - timedelta(days=months_ago * 30)
                bar = (
                    await session.execute(
                        select(PriceHistory.trade_date, PriceHistory.close)
                        .where(
                            PriceHistory.security_id == sec.id,
                            PriceHistory.trade_date >= target,
                        )
                        .order_by(PriceHistory.trade_date)
                        .limit(1)
                    )
                ).first()
                if bar is None:
                    logger.warning("no bar for %s near %s — skipping", ticker, target)
                    continue
                shares = lots * 100
                rate = BUY_FEE_RATE if txn_type == "BUY" else SELL_FEE_RATE
                session.add(
                    Transaction(
                        portfolio_id=portfolio.id,
                        security_id=sec.id,
                        type=txn_type,
                        shares=shares,
                        price_per_share=bar.close,
                        fee=round(shares * bar.close * rate),
                        executed_at=bar.trade_date,
                        note="demo seed",
                    )
                )
                print(
                    f"  {bar.trade_date}  {txn_type:4} {ticker:5} {lots:>3} lots "
                    f"@ {bar.close:,}"
                )

    # 5. Quotes for the held tickers + fundamentals, so the UI is complete
    print("Refreshing quotes…")
    await sync_quotes()
    print("Fetching fundamentals…")
    await sync_fundamentals(TICKERS)

    print()
    print("Demo template ready.")
    print("  Visitors click 'Explore the demo portfolio' and POST /auth/demo")
    print("  hands each of them a private clone of it. There is no shared")
    print("  password to hand out, and nothing a visitor does can reach this")
    print("  template — so it stays presentable without a re-seed cron.")


if __name__ == "__main__":
    asyncio.run(main())
