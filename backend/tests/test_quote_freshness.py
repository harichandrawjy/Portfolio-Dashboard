"""A quote is only current while it is newer than the last published bar.

`latest_quotes` is refreshed only for tickers someone HOLDS, while
`price_history` is refreshed for anything with history. A ticker that was
backfilled by someone opening its page, and never bought, therefore keeps a
frozen quote next to bars that stay current — and every held ticker hits a
one-night version of the same thing between the 18:30 bar job and the next
morning's first quote.

`quote_trade_date` is what lets a caller tell the two apart, so these pin it.
The provisional-bar gate in routers/securities.py already encodes the same
rule; the point here is that the detail endpoint reports enough to apply it.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import LatestQuote, PriceHistory, Security

from .helpers import FUNDING_DATE  # noqa: F401  (keeps helper import parity)

pytestmark = pytest.mark.asyncio(loop_scope="session")

TICKER = "TLKM"  # seeded bare by conftest: no bars, no quote


async def _seed(bar_date: date, quote_date: date | None, quote_price: int) -> None:
    """Give TLKM exactly one bar and one quote, at the dates asked for."""
    async with SessionLocal() as session:
        async with session.begin():
            sec = await session.scalar(
                select(Security).where(Security.ticker == TICKER)
            )
            await session.execute(
                delete(PriceHistory).where(PriceHistory.security_id == sec.id)
            )
            await session.execute(
                delete(LatestQuote).where(LatestQuote.security_id == sec.id)
            )
            session.add(
                PriceHistory(
                    security_id=sec.id, trade_date=bar_date,
                    open=3000, high=3100, low=2950, close=3050, volume=1_000,
                )
            )
            session.add(
                LatestQuote(
                    security_id=sec.id,
                    price=quote_price,
                    trade_date=quote_date,
                    as_of=datetime(2026, 7, 17, 8, 49, tzinfo=timezone.utc),
                )
            )


async def _cleanup() -> None:
    async with SessionLocal() as session:
        async with session.begin():
            sec = await session.scalar(
                select(Security).where(Security.ticker == TICKER)
            )
            await session.execute(
                delete(PriceHistory).where(PriceHistory.security_id == sec.id)
            )
            await session.execute(
                delete(LatestQuote).where(LatestQuote.security_id == sec.id)
            )


async def _detail(client):
    from .test_stocks import _login

    auth = await _login(client, "putra@example.com")
    r = await client.get(f"/securities/{TICKER}", headers=auth)
    assert r.status_code == 200
    return r.json()


async def test_live_session_quote_is_newer_than_the_last_bar(client):
    """Mid-session: today has no settled bar yet, so the quote leads."""
    await _seed(bar_date=date(2026, 7, 17), quote_date=date(2026, 7, 18), quote_price=3200)
    try:
        body = await _detail(client)
        assert body["quote_trade_date"] == "2026-07-18"
        assert body["last_close_date"] == "2026-07-17"
        # Strictly newer -> a caller should show the quote.
        assert body["quote_trade_date"] > body["last_close_date"]
        assert body["quote_price"] == 3200
    finally:
        await _cleanup()


async def test_after_the_bar_settles_the_quote_is_not_newer(client):
    """After 18:30 the bar exists for the same date the quote came from.

    Equal dates, and the bar is the later of the two — this is the case that
    had the header showing 268 while the holdings table showed the 270 close.
    """
    await _seed(bar_date=date(2026, 7, 17), quote_date=date(2026, 7, 17), quote_price=3020)
    try:
        body = await _detail(client)
        assert body["quote_trade_date"] == body["last_close_date"] == "2026-07-17"
        # NOT strictly newer -> the settled close wins.
        assert not (body["quote_trade_date"] > body["last_close_date"])
        assert body["last_close"] == 3050
    finally:
        await _cleanup()


async def test_abandoned_ticker_keeps_a_frozen_quote_beside_current_bars(client):
    """Backfilled by a page view, never held: bars move on, the quote does not."""
    await _seed(bar_date=date(2026, 7, 17), quote_date=date(2026, 7, 12), quote_price=2800)
    try:
        body = await _detail(client)
        # Five days behind the bar — reporting it as the price would be wrong
        # by however far the stock moved since.
        assert body["quote_trade_date"] < body["last_close_date"]
        assert body["quote_price"] == 2800
        assert body["last_close"] == 3050
    finally:
        await _cleanup()


async def test_quote_trade_date_is_null_when_there_is_no_quote(client):
    async with SessionLocal() as session:
        async with session.begin():
            sec = await session.scalar(
                select(Security).where(Security.ticker == TICKER)
            )
            await session.execute(
                delete(LatestQuote).where(LatestQuote.security_id == sec.id)
            )
            session.add(
                PriceHistory(
                    security_id=sec.id, trade_date=date(2026, 7, 17),
                    open=3000, high=3100, low=2950, close=3050, volume=1_000,
                )
            )
    try:
        body = await _detail(client)
        assert body["quote_trade_date"] is None
        assert body["quote_price"] is None
        assert body["last_close"] == 3050
    finally:
        await _cleanup()
