from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.deps import CurrentUser, Session
from app.models import Security
from app.schemas import SecuritySearchOut

router = APIRouter(tags=["securities"])

SEARCH_LIMIT = 10


@router.get("/securities/search", response_model=list[SecuritySearchOut])
async def search_securities(
    user: CurrentUser,
    session: Session,
    q: str = Query(min_length=1, max_length=50),
) -> list[Security]:
    """Autocomplete over the local IDX universe — never an external call.

    Prefix match on ticker (BB -> BBCA, BBRI...), substring match on
    company name (central -> Bank Central Asia). Active stocks only.
    Tickers without price history still appear: history is backfilled
    lazily AFTER a user first picks one.
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

    result = await session.scalars(
        select(Security)
        .where(
            Security.kind == "stock",
            Security.is_active.is_(True),
            or_(
                Security.ticker.like(prefix),
                Security.name.ilike(substring),
            ),
        )
        # ticker-prefix hits first, then alphabetical
        .order_by(Security.ticker.like(prefix).desc(), Security.ticker)
        .limit(SEARCH_LIMIT)
    )
    return list(result)
