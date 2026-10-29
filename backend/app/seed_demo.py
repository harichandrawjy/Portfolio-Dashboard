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
from math import ceil
from typing import NamedTuple

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
# Defined in app/demo.py, because that is what looks the portfolios up when
# cloning them for a visitor. One definition: if these two ever disagreed, the
# seed would build portfolios the demo endpoint could not find, and the only
# symptom would be a 503 from a database that looks correctly seeded.
PORTFOLIO_NAME = TEMPLATE_PORTFOLIO_NAME


class DemoPortfolio(NamedTuple):
    """One seeded portfolio. `script` is (ticker, months_ago, type, lots)."""

    name: str
    description: str
    # None = size it from what the trades actually cost (see `_size_deposit`).
    # An explicit figure is only for a portfolio already seeded in the wild,
    # whose numbers must not move under people who have seen them.
    deposit: int | None
    script: list[tuple[str, int, str, int]]


# THREE PORTFOLIOS, DRAWN FROM ONE SET OF TICKERS.
#
# Every holding below is already in the flagship's ticker list, which is the
# whole reason the extra two are free: `backfill_ticker` is the slow, fragile
# step (yfinance throttles datacenter IPs hard — see DEPLOY.md), and reusing
# the same eight names means adding portfolios costs no network at all. New
# tickers would be richer, and would also make seeding a fresh box slower and
# able to fail in a new way. The variety that the UI actually exercises comes
# from weights, timing and size, not from ticker novelty.
#
# They differ on purpose, because the demo is what carries a reviewer
# (PRODUCT.md principle 5), and one portfolio only ever shows one shape:
#
#   Blue Chips        eight holdings, two years, buys and sells — the flagship
#   Defensive Income  three low-beta names, buy-and-hold, no sells at all
#   Concentrated Bet  two holdings, recent, deliberately lopsided
#
# Two holdings is the frontier's minimum, so Concentrated Bet also keeps that
# boundary exercised rather than only ever being hit by accident.
PORTFOLIOS: list[DemoPortfolio] = [
    DemoPortfolio(
        name=TEMPLATE_PORTFOLIO_NAME,
        description="Seeded demo: IDX large caps traded over two years",
        # The scripted buys cost ~Rp 86M and the sells return ~Rp 5M, leaving
        # a realistic leftover cash balance.
        deposit=100_000_000,
        script=[
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
        ],
    ),
    DemoPortfolio(
        name="Defensive Income (demo)",
        description="Seeded demo: low-beta IDX names, bought and held",
        deposit=None,
        script=[
            ("SIDO", 18, "BUY", 100),
            ("TLKM", 18, "BUY", 40),
            ("ASII", 15, "BUY", 20),
            ("SIDO", 9, "BUY", 50),
            ("TLKM", 4, "BUY", 20),
        ],
    ),
    DemoPortfolio(
        name="Concentrated Bet (demo)",
        description="Seeded demo: two holdings, deliberately lopsided",
        deposit=None,
        script=[
            ("BMRI", 8, "BUY", 20),
            ("GOTO", 8, "BUY", 300),
            ("GOTO", 3, "BUY", 200),
            ("BMRI", 1, "SELL", 5),
        ],
    ),
]

TICKERS = sorted({t for p in PORTFOLIOS for t, *_ in p.script})
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


def _size_deposit(trades: list[tuple[Security, int, int, str, date]]) -> int:
    """The smallest tidy opening deposit that keeps the cash ledger positive.

    Walks the resolved trades in date order from a zero balance and takes the
    deepest point the running total reaches — that is what the portfolio has
    to be funded with. Adds a tenth on top so it ends holding some cash rather
    than exactly none, and rounds up to the nearest 5M so the figure reads as
    a decision somebody made rather than the output of a calculation.

    The margin is deliberately thin. At a fifth, plus the rounding step, the
    smaller portfolios ended up sitting on 25-45% cash — which quietly
    contradicts what they are there to show, since a two-holding
    "concentrated bet" holding half its value in cash is not concentrated.

    This exists because the trade prices are real closes looked up by date,
    and those dates slide forward on every run: what the script costs drifts
    with the market, so any hardcoded deposit is a guess with a shelf life.
    """
    balance = 0
    deepest = 0
    for _sec, shares, price, txn_type, _trade_date in sorted(
        trades, key=lambda t: t[4]
    ):
        gross = shares * price
        if txn_type == "BUY":
            balance -= gross + round(gross * BUY_FEE_RATE)
        else:
            balance += gross - round(gross * SELL_FEE_RATE)
        deepest = min(deepest, balance)

    if deepest >= 0:  # a script that never spends more than it has
        return 0
    step = 5_000_000
    return ceil(-deepest * 1.1 / step) * step


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

        # IDEMPOTENT PER PORTFOLIO, not per template account.
        #
        # This used to return as soon as the flagship existed, which was fine
        # while that was the whole demo and is actively wrong now: every
        # already-deployed database has the flagship, so an all-or-nothing
        # check means the portfolios added here would never appear on the box
        # that most needs them. Seed whatever is missing and leave the rest
        # alone — re-running stays safe, and it becomes the upgrade path.
        wanted = [p.name for p in PORTFOLIOS]
        if user is not None:
            present = set(
                (
                    await session.scalars(
                        select(Portfolio.name).where(
                            Portfolio.user_id == user.id,
                            Portfolio.name.in_(wanted),
                        )
                    )
                ).all()
            )
        else:
            present = set()

        todo = [p for p in PORTFOLIOS if p.name not in present]
        if not todo:
            print("Demo template already seeded — visitors get their own clone.")
            return
        for name in sorted(present):
            print(f"Already present, leaving alone: {name}")

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

            for spec in todo:
                print(f"\nSeeding {spec.name}…")
                portfolio = Portfolio(
                    user_id=user.id,
                    name=spec.name,
                    description=spec.description,
                )
                session.add(portfolio)
                await session.flush()

                # RESOLVE EVERY TRADE FIRST, THEN SIZE THE DEPOSIT.
                #
                # The prices below are real closes looked up by date, and the
                # dates slide forward every day this is run, so what the script
                # costs is not a constant — it drifts with the market. A
                # hardcoded deposit is therefore a guess with a shelf life: too
                # small and the portfolio seeds with a negative cash balance,
                # which is not a state a real ledger can reach and looks like a
                # bug to anyone reading the demo.
                #
                # Resolving first makes the deposit a fact about the trades
                # rather than a guess about them. `deposit=None` asks for that;
                # the flagship keeps its explicit 100M because it is already
                # seeded everywhere and its figures should not move.
                resolved: list[tuple[Security, int, int, str, date]] = []
                for ticker, months_ago, txn_type, lots in spec.script:
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
                    resolved.append(
                        (sec, lots * 100, bar.close, txn_type, bar.trade_date)
                    )

                deposit = spec.deposit or _size_deposit(resolved)

                # Dated a week before the earliest trade so the cash is already
                # there when the first buy lands.
                oldest = max(months_ago for _, months_ago, _, _ in spec.script)
                session.add(
                    CashFlow(
                        portfolio_id=portfolio.id,
                        type="DEPOSIT",
                        amount=deposit,
                        occurred_at=today - timedelta(days=oldest * 30 + 7),
                        note="opening deposit",
                    )
                )
                print(f"  deposit {deposit:,}")

                for sec, shares, price, txn_type, trade_date in resolved:
                    rate = BUY_FEE_RATE if txn_type == "BUY" else SELL_FEE_RATE
                    session.add(
                        Transaction(
                            portfolio_id=portfolio.id,
                            security_id=sec.id,
                            type=txn_type,
                            shares=shares,
                            price_per_share=price,
                            fee=round(shares * price * rate),
                            executed_at=trade_date,
                            note="demo seed",
                        )
                    )
                    print(
                        f"  {trade_date}  {txn_type:4} {sec.ticker:5} "
                        f"{shares // 100:>3} lots @ {price:,}"
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
