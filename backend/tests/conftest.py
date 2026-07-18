"""Test harness: run everything against a throwaway portfolio_test database.

The env override happens at import time, BEFORE any app module is imported,
because app.config caches settings and app.db builds its engine on import.
"""

import asyncio
import os

# --- must run before any `app.*` import -----------------------------------
_ADMIN_URL = os.environ["DATABASE_URL"]  # the dev database; used only for CREATE/DROP
_TEST_DB = "portfolio_test"
_TEST_URL = _ADMIN_URL.rsplit("/", 1)[0] + f"/{_TEST_DB}"
os.environ["DATABASE_URL"] = _TEST_URL
# ---------------------------------------------------------------------------

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _admin_exec(*statements: str) -> None:
    engine = create_async_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Fresh test DB with the real Alembic-applied schema; dropped afterwards."""
    asyncio.run(
        _admin_exec(
            f"DROP DATABASE IF EXISTS {_TEST_DB} WITH (FORCE)",
            f"CREATE DATABASE {_TEST_DB}",
        )
    )

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")

    yield

    asyncio.run(_admin_exec(f"DROP DATABASE IF EXISTS {_TEST_DB} WITH (FORCE)"))


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def _dispose_engine():
    """Close the app engine's pool while the session loop still exists."""
    yield
    from app.db import engine

    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def client(_database):
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def seed_market_data(_database):
    """A tiny known universe: BBCA (with history + quote) and TLKM (bare)."""
    from datetime import date, datetime, timezone

    from app.db import SessionLocal
    from app.models import LatestQuote, PriceHistory, Security

    async with SessionLocal() as session:
        async with session.begin():
            bbca = Security(
                ticker="BBCA", yahoo_symbol="BBCA.JK",
                name="Bank Central Asia Tbk.", kind="stock",
                sector="Keuangan", board="Main",
            )
            tlkm = Security(
                ticker="TLKM", yahoo_symbol="TLKM.JK",
                name="Telkom Indonesia (Persero) Tbk", kind="stock",
                sector="Infrastruktur", board="Main",
            )
            ihsg = Security(
                ticker="IHSG", yahoo_symbol="^JKSE",
                name="Indeks Harga Saham Gabungan (IHSG)", kind="index",
            )
            session.add_all([bbca, tlkm, ihsg])
            await session.flush()
            session.add(
                PriceHistory(
                    security_id=bbca.id, trade_date=date(2026, 7, 17),
                    open=6900, high=7050, low=6850, close=7000, volume=1_000_000,
                )
            )
            session.add(
                LatestQuote(
                    security_id=bbca.id, price=7000, change_pct=None,
                    as_of=datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc),
                )
            )
    yield
