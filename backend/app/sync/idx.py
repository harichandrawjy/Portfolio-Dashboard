"""IDX website JSON client — metadata only (which stocks exist, not prices).

IDX sits behind Cloudflare bot management; depending on the network these
endpoints may 403 regardless of headers. Callers must treat a fetch failure
as an expected condition and keep existing data (see universe.py) — a failed
fetch must never clobber the securities table.
"""

import asyncio
import logging
import random

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

STOCK_LIST_PATH = "/primary/StockData/GetSecuritiesStock"
PROFILES_PATH = "/primary/ListedCompany/GetCompanyProfiles"

# IDX's WAF rejects clients that don't look like a browser.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "Referer": "https://www.idx.co.id/en/market-data/stocks-data/stock-list/",
    "X-Requested-With": "XMLHttpRequest",
}

RETRY_ATTEMPTS = 4
RETRY_BASE_DELAY = 2.0  # seconds; doubles per attempt, with jitter

# IDX lists ~950 stocks; far fewer than this means a partial or garbage
# response that must not be allowed to reach the database.
MIN_EXPECTED_STOCKS = 700


class IdxFetchError(Exception):
    """Raised when IDX cannot be fetched or returns an unusable payload."""


async def _get_json(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY * 2 ** (attempt - 1) * random.uniform(0.8, 1.2)
                logger.warning(
                    "IDX request %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    path, attempt, RETRY_ATTEMPTS, exc, delay,
                )
                await asyncio.sleep(delay)
    raise IdxFetchError(
        f"IDX request {path} failed after {RETRY_ATTEMPTS} attempts"
    ) from last_exc


async def fetch_universe() -> list[dict]:
    """Fetch every listed stock: [{ticker, name, sector, board}, ...].

    The stock list endpoint is authoritative for what exists; the company
    profiles endpoint enriches it with the IDX-IC sector. Sector data is
    best-effort: if only the profiles call fails we still sync, with
    sector=None meaning "leave existing sector untouched".
    """
    settings = get_settings()
    async with httpx.AsyncClient(
        base_url=settings.idx_base_url,
        headers=HEADERS,
        timeout=30,
        follow_redirects=True,
    ) as client:
        stock_payload = await _get_json(
            client,
            STOCK_LIST_PATH,
            {"start": 0, "length": 9999, "code": "", "sector": "", "board": "", "language": "en-us"},
        )
        stocks = stock_payload.get("data") or []
        if len(stocks) < MIN_EXPECTED_STOCKS:
            raise IdxFetchError(
                f"IDX returned only {len(stocks)} stocks (expected >= {MIN_EXPECTED_STOCKS}); "
                "refusing to sync from a partial response"
            )

        sector_by_code: dict[str, str] = {}
        try:
            profile_payload = await _get_json(
                client,
                PROFILES_PATH,
                {"start": 0, "length": 9999, "emitenType": "s", "language": "en-us"},
            )
            for p in profile_payload.get("data") or []:
                code = (p.get("KodeEmiten") or "").strip()
                sector = (p.get("Sektor") or "").strip()
                if code and sector:
                    sector_by_code[code] = sector
        except IdxFetchError:
            logger.warning("IDX profiles fetch failed — syncing universe without sector updates")

        rows = []
        for s in stocks:
            ticker = (s.get("Code") or "").strip()
            name = (s.get("Name") or "").strip()
            if not ticker or not name:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "sector": sector_by_code.get(ticker),
                    "board": (s.get("ListingBoard") or "").strip() or None,
                }
            )
        return rows
