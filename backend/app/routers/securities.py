from fastapi import APIRouter, Query
from sqlalchemy import text as sa_text

from app.deps import CurrentUser, Session
from app.schemas import SecuritySearchOut

router = APIRouter(tags=["securities"])

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
