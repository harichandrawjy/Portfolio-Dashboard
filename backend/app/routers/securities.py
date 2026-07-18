import logging

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy import text as sa_text

from app.deps import CurrentUser, Session
from app.models import PriceHistory, Security
from app.scheduler import enqueue_backfill
from app.schemas import EnsurePricesOut, SecuritySearchOut

router = APIRouter(tags=["securities"])
logger = logging.getLogger(__name__)

SEARCH_LIMIT = 10


@router.get("/securities/search", response_model=list[SecuritySearchOut])
async def search_securities(
    user: CurrentUser,
    session: Session,
    q: str = Query(min_length=1, max_length=50),
) -> list[SecuritySearchOut]:
    """Autocomplete over the local IDX universe — never an external call.

    Prefix match on ticker (BB -> BBCA, BBRI...), substring match on
    company name (central -> Bank Central Asia). Active stocks only.
    Tickers without price history still appear: history is backfilled
    lazily AFTER a user first picks one.

    last_price is the latest quote, falling back to the most recent
    stored close — the frontend uses it to pre-fill transaction entry.
    """
    term = q.strip()
    if not term:
        return []
    # escape LIKE wildcards so a literal '%' in input can't scan everything
    escaped = (
        term.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
    )
    prefix = escaped.upper() + "%"
    substring = f"%{escaped}%"

    rows = await session.execute(
        sa_text(
            """
            SELECT s.ticker, s.name, s.sector, s.board,
                   COALESCE(q.price, ph.close) AS last_price
            FROM securities s
            LEFT JOIN latest_quotes q ON q.security_id = s.id
            LEFT JOIN LATERAL (
                SELECT close FROM price_history p
                WHERE p.security_id = s.id
                ORDER BY p.trade_date DESC LIMIT 1
            ) ph ON TRUE
            WHERE s.kind = 'stock' AND s.is_active
              AND (s.ticker LIKE :prefix OR s.name ILIKE :substring)
            ORDER BY (s.ticker LIKE :prefix) DESC, s.ticker
            LIMIT :lim
            """
        ),
        {"prefix": prefix, "substring": substring, "lim": SEARCH_LIMIT},
    )
    return [SecuritySearchOut(**m) for m in rows.mappings()]


@router.post("/securities/{ticker}/ensure-prices", response_model=EnsurePricesOut)
async def ensure_prices(
    ticker: str, user: CurrentUser, session: Session
) -> EnsurePricesOut:
    """Kick off the lazy 5y backfill for a ticker that has no local prices.

    Called when a user picks a never-priced ticker (transaction form, and
    later the stock detail page). Never fetches inline — it only enqueues
    the Step-3 background job; the client polls local data afterwards.
    """
    sec = await session.scalar(
        select(Security).where(Security.ticker == ticker.upper())
    )
    if sec is None or sec.kind != "stock":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown ticker")

    has_history = await session.scalar(
        select(PriceHistory.security_id)
        .where(PriceHistory.security_id == sec.id)
        .limit(1)
    )
    if has_history is not None:
        return EnsurePricesOut(status="ready")
    try:
        enqueue_backfill(sec.ticker)
    except RuntimeError:
        logger.error("scheduler unavailable — cannot backfill %s on demand", sec.ticker)
        return EnsurePricesOut(status="unavailable")
    return EnsurePricesOut(status="queued")
