"""Universe sync — keep the securities table in step with what IDX lists.

Failure philosophy (in order of trust):
  1. Live IDX fetch succeeded  -> full sync: insert new listings, update
     changed names/sectors/boards, deactivate vanished tickers. One
     transaction; rows are never deleted (users may hold delisted stock).
  2. Live fetch failed         -> loud log, then seed from the bundled CSV
     snapshot, INSERT-ONLY. The snapshot ages, so it is never allowed to
     update or deactivate anything — on a populated database the fallback
     is a no-op; on a fresh clone it seeds ~950 tickers without network.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Security
from app.sync.idx import IdxFetchError, fetch_universe

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "idx_universe.csv"

BENCHMARK = {
    "ticker": "IHSG",
    "yahoo_symbol": "^JKSE",
    "name": "Indeks Harga Saham Gabungan (IHSG)",
    "kind": "index",
}


@dataclass
class SyncResult:
    source: str  # "idx" | "csv-fallback"
    inserted: int = 0
    updated: int = 0
    deactivated: int = 0
    total_active: int = 0


async def sync_universe() -> SyncResult:
    try:
        rows = await fetch_universe()
    except IdxFetchError:
        logger.exception(
            "IDX UNIVERSE FETCH FAILED — existing securities are untouched; "
            "attempting bundled CSV snapshot (insert-only)"
        )
        return await _seed_from_csv()
    return await _apply_full_sync(rows)


async def _apply_full_sync(rows: list[dict]) -> SyncResult:
    fetched = {row["ticker"]: row for row in rows}
    result = SyncResult(source="idx")

    async with SessionLocal() as session:
        async with session.begin():
            await _ensure_benchmark(session)

            existing = {
                s.ticker: s
                for s in await session.scalars(
                    select(Security).where(Security.kind == "stock")
                )
            }

            for ticker, row in fetched.items():
                sec = existing.get(ticker)
                if sec is None:
                    session.add(
                        Security(
                            ticker=ticker,
                            yahoo_symbol=f"{ticker}.JK",
                            name=row["name"],
                            kind="stock",
                            sector=row["sector"],
                            board=row["board"],
                            is_active=True,
                        )
                    )
                    result.inserted += 1
                    continue

                changed = False
                if sec.name != row["name"]:
                    sec.name = row["name"]
                    changed = True
                # None means "source had no data" — never blank out a known value
                if row["sector"] is not None and sec.sector != row["sector"]:
                    sec.sector = row["sector"]
                    changed = True
                if row["board"] is not None and sec.board != row["board"]:
                    sec.board = row["board"]
                    changed = True
                if not sec.is_active:  # relisting
                    sec.is_active = True
                    changed = True
                if changed:
                    result.updated += 1

            for ticker, sec in existing.items():
                if ticker not in fetched and sec.is_active:
                    sec.is_active = False
                    result.deactivated += 1

        result.total_active = await _count_active(session)

    logger.info(
        "universe sync (live IDX): +%d inserted, %d updated, %d deactivated, %d active stocks",
        result.inserted, result.updated, result.deactivated, result.total_active,
    )
    return result


async def _seed_from_csv() -> SyncResult:
    if not CSV_PATH.exists():
        logger.critical("CSV fallback missing at %s — universe left as-is", CSV_PATH)
        return SyncResult(source="csv-fallback")

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("ticker")]

    logger.warning(
        "FALLBACK PATH: seeding universe from bundled CSV snapshot (%s, %d rows) — "
        "insert-only, except for repairing names the snapshot proves were truncated",
        CSV_PATH.name, len(rows),
    )

    result = SyncResult(source="csv-fallback")
    async with SessionLocal() as session:
        async with session.begin():
            await _ensure_benchmark(session)
            by_ticker = {
                s.ticker: s
                for s in (
                    await session.scalars(
                        select(Security).where(Security.kind == "stock")
                    )
                ).all()
            }
            for row in rows:
                current = by_ticker.get(row["ticker"])
                if current is not None:
                    if _is_truncation_of(current.name, row["name"]):
                        # Append only the sliced-off tail, so the stored
                        # casing survives even if the snapshot shouts.
                        current.name += row["name"][len(current.name) :]
                        result.updated += 1
                    continue
                session.add(
                    Security(
                        ticker=row["ticker"],
                        yahoo_symbol=f"{row['ticker']}.JK",
                        name=row["name"],
                        kind="stock",
                        sector=row.get("sector") or None,
                        board=row.get("board") or None,
                        is_active=True,
                    )
                )
                result.inserted += 1

        result.total_active = await _count_active(session)

    logger.info(
        "universe seed (CSV fallback): +%d inserted, %d name(s) un-truncated, "
        "%d active stocks",
        result.inserted, result.updated, result.total_active,
    )
    return result


def _is_truncation_of(stored: str, snapshot: str) -> bool:
    """Is `stored` the same name as `snapshot`, with the tail cut off?

    The one exception to this path being insert-only, and deliberately the
    narrowest one that fixes the problem.

    IDX's stock-list endpoint cuts Name at 30 characters, so a database seeded
    from the snapshot carries "Abadi Nusantara Hijau Investam" where the real
    name is "Abadi Nusantara Hijau Investama Tbk". Every name in a
    CSV-seeded deployment was clipped that way, because the live fetch — the
    only path that enriches from the profiles endpoint — 403s from a
    datacenter IP and never runs there.

    Insert-only exists so an ageing snapshot cannot overwrite fresher live
    data. Restoring characters that were sliced off the end is not competing
    with fresher data: it is the same name, less damaged. The guard is
    strictly "one is a prefix of the other and shorter", so a genuinely
    different name can never be written over a good one — which matters,
    because plenty of real names are exactly 30 characters and complete
    ("Akasha Wira International Tbk."), and length alone would have condemned
    them.

    Case-insensitive because IDX shouts some names in the profiles feed; the
    stored value keeps the casing the caller already has.
    """
    if not stored or not snapshot or len(snapshot) <= len(stored):
        return False
    return snapshot.lower().startswith(stored.lower())


async def _ensure_benchmark(session) -> None:
    """The ^JKSE index row must always exist (kind='index', never deactivated)."""
    found = await session.scalar(
        select(Security.id).where(Security.yahoo_symbol == BENCHMARK["yahoo_symbol"])
    )
    if found is None:
        session.add(Security(**BENCHMARK, is_active=True))
        logger.info("inserted benchmark index row %s", BENCHMARK["yahoo_symbol"])


async def _count_active(session) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(Security)
        .where(Security.kind == "stock", Security.is_active.is_(True))
    )
