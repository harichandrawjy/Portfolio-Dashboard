import logging
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser, Session
from app.models import (
    FinancialStatement,
    Fundamentals,
    LatestQuote,
    PriceHistory,
    Security,
    SecurityStats,
)
from app.performance import RANGE_DAYS, RangeKey
from app.scheduler import enqueue_backfill
from app.schemas import (
    CloseOnDateOut,
    DerivedMetricsOut,
    EnsurePricesOut,
    FinancialsOut,
    FundamentalsOut,
    PositionRow,
    PositionTxn,
    SecurityDetailOut,
    SecuritySearchOut,
    SecurityStatsOut,
    StatementPeriodOut,
    StockPositionOut,
    ProvisionalBar,
    StockPricePoint,
    StockPricesOut,
)
from app.sync.prices import drop_holiday_placeholders
from app.sync.statements import compute_derived

router = APIRouter(tags=["securities"])
logger = logging.getLogger(__name__)

SEARCH_LIMIT = 10
JAKARTA = ZoneInfo("Asia/Jakarta")


async def _get_stock(ticker: str, session: AsyncSession) -> Security:
    sec = await session.scalar(
        select(Security).where(Security.ticker == ticker.upper())
    )
    if sec is None or sec.kind != "stock":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown ticker")
    return sec


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
    sec = await _get_stock(ticker, session)

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


@router.get("/securities/{ticker}", response_model=SecurityDetailOut)
async def security_detail(
    ticker: str, user: CurrentUser, session: Session
) -> SecurityDetailOut:
    """Profile + quote + cached stats. Nothing here computes over price
    rows at request time: stats come from security_stats (nightly cache,
    also refreshed right after a first-use backfill)."""
    sec = await _get_stock(ticker, session)

    quote = await session.get(LatestQuote, sec.id)
    last_bar = (
        await session.execute(
            select(PriceHistory.trade_date, PriceHistory.close)
            .where(PriceHistory.security_id == sec.id)
            .order_by(PriceHistory.trade_date.desc())
            .limit(1)
        )
    ).first()
    stats = await session.get(SecurityStats, sec.id)
    fundamentals = await session.get(Fundamentals, sec.id)

    return SecurityDetailOut(
        ticker=sec.ticker,
        name=sec.name,
        sector=sec.sector,
        board=sec.board,
        is_active=sec.is_active,
        has_history=last_bar is not None,
        quote_price=quote.price if quote else None,
        quote_change_pct=(
            float(quote.change_pct) if quote and quote.change_pct is not None else None
        ),
        quote_as_of=quote.as_of if quote else None,
        quote_trade_date=quote.trade_date if quote else None,
        last_close=last_bar.close if last_bar else None,
        last_close_date=last_bar.trade_date if last_bar else None,
        stats=SecurityStatsOut.model_validate(stats) if stats else None,
        fundamentals=(
            FundamentalsOut.model_validate(fundamentals) if fundamentals else None
        ),
    )


@router.get("/securities/{ticker}/financials", response_model=FinancialsOut)
async def security_financials(
    ticker: str, user: CurrentUser, session: Session
) -> FinancialsOut:
    """Stored statement periods + metrics derived from them. The derivation
    is a pure function over <=10 small dicts — cheap enough per request."""
    sec = await _get_stock(ticker, session)

    rows = list(
        await session.scalars(
            select(FinancialStatement)
            .where(FinancialStatement.security_id == sec.id)
            .order_by(FinancialStatement.period_end.desc())
        )
    )
    annual = [r for r in rows if r.period_type == "annual"][:5]
    quarterly = [r for r in rows if r.period_type == "quarterly"][:6]

    fund = await session.get(Fundamentals, sec.id)
    currency = None
    if fund and fund.extra:
        currency = fund.extra.get("financial_currency")
    idr_reporter = currency in (None, "IDR")

    derived = compute_derived(
        [r.items for r in quarterly],
        [r.items for r in annual],
        fund.market_cap if fund else None,
        idr_reporter,
    )

    def _periods(items: list[FinancialStatement]) -> list[StatementPeriodOut]:
        return [
            StatementPeriodOut(period_end=r.period_end, items=r.items) for r in items
        ]

    return FinancialsOut(
        ticker=sec.ticker,
        currency=currency,
        annual=_periods(annual),
        quarterly=_periods(quarterly),
        derived=DerivedMetricsOut(**derived),
    )


@router.get("/securities/{ticker}/close", response_model=CloseOnDateOut)
async def security_close_on(
    ticker: str,
    user: CurrentUser,
    session: Session,
    on: date = Query(description="trade date, YYYY-MM-DD"),
) -> CloseOnDateOut:
    """The close on `on`, or the last trading day before it.

    Used to price a back-dated transaction. Falling back to the previous
    bar matters because users pick weekends and IDX holidays, when no bar
    exists; the response reports which date was actually used.
    """
    sec = await _get_stock(ticker, session)
    bar = (
        await session.execute(
            select(PriceHistory.trade_date, PriceHistory.close)
            .where(
                PriceHistory.security_id == sec.id,
                PriceHistory.trade_date <= on,
            )
            .order_by(PriceHistory.trade_date.desc())
            .limit(1)
        )
    ).first()
    return CloseOnDateOut(
        ticker=sec.ticker,
        requested=on,
        trade_date=bar.trade_date if bar else None,
        close=bar.close if bar else None,
    )


@router.get("/securities/{ticker}/prices", response_model=StockPricesOut)
async def security_prices(
    ticker: str,
    user: CurrentUser,
    session: Session,
    range_key: RangeKey = Query(default="1y", alias="range"),
) -> StockPricesOut:
    """Daily close series for the chart, with the IHSG rebased to the
    stock's first close in range so both overlay on one axis."""
    sec = await _get_stock(ticker, session)

    today = datetime.now(JAKARTA).date()
    start = None if range_key == "all" else today - timedelta(days=RANGE_DAYS[range_key])

    stmt = (
        select(
            PriceHistory.trade_date,
            PriceHistory.open,
            PriceHistory.high,
            PriceHistory.low,
            PriceHistory.close,
            PriceHistory.volume,
        )
        .where(PriceHistory.security_id == sec.id)
        .order_by(PriceHistory.trade_date)
    )
    if start is not None:
        stmt = stmt.where(PriceHistory.trade_date >= start)
    bars = (await session.execute(stmt)).all()

    ihsg_by_date = {}
    if bars:
        benchmark_id = await session.scalar(
            select(Security.id).where(Security.yahoo_symbol == "^JKSE")
        )
        if benchmark_id is not None:
            rows = await session.execute(
                select(PriceHistory.trade_date, PriceHistory.close).where(
                    PriceHistory.security_id == benchmark_id,
                    PriceHistory.trade_date >= bars[0].trade_date,
                )
            )
            ihsg_by_date = {d: c for d, c in rows}

    # Rows written before the sync-side guard existed, plus anything its
    # fail-open path lets through, are refused here too. See the docstring
    # on drop_holiday_placeholders for why both conditions are needed.
    bars = drop_holiday_placeholders(bars, ihsg_by_date.keys())

    points: list[StockPricePoint] = []
    ihsg_base: int | None = None
    for bar in bars:
        ihsg_close = ihsg_by_date.get(bar.trade_date)
        if ihsg_base is None and ihsg_close is not None:
            ihsg_base = ihsg_close
        rebased = (
            round(ihsg_close / ihsg_base * bars[0].close)
            if ihsg_close is not None and ihsg_base
            else None
        )
        points.append(
            StockPricePoint(
                date=bar.trade_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                ihsg=rebased,
            )
        )

    # Today's session, if one is actually in progress. Gated on the quote's
    # own trade_date being NEWER than the last published bar — that single
    # condition covers both ways this could mislead: a stale quote left over
    # from a previous session, and the window after 18:30 when the real bar
    # exists and a provisional copy would duplicate it.
    provisional = None
    quote = await session.scalar(
        select(LatestQuote).where(LatestQuote.security_id == sec.id)
    )
    newest_bar = bars[-1].trade_date if bars else None
    if (
        quote is not None
        and quote.trade_date is not None
        and (newest_bar is None or quote.trade_date > newest_bar)
    ):
        provisional = ProvisionalBar(
            date=quote.trade_date,
            open=quote.open,
            high=quote.high,
            low=quote.low,
            close=quote.price,
            volume=quote.volume,
            as_of=quote.as_of,
        )

    return StockPricesOut(
        ticker=sec.ticker,
        range=range_key,
        points=points,
        provisional=provisional,
    )


@router.get("/securities/{ticker}/position", response_model=StockPositionOut)
async def security_position(
    ticker: str, user: CurrentUser, session: Session
) -> StockPositionOut:
    """The logged-in user's position in this stock across their portfolios,
    plus their trade dates for chart markers. held=false -> no panel."""
    sec = await _get_stock(ticker, session)

    pos_rows = (
        await session.execute(
            sa_text(
                """
                SELECT p.id AS portfolio_id, p.name AS portfolio_name,
                       h.shares, h.avg_cost_per_share,
                       COALESCE(q.price, ph.close) AS last_price,
                       totals.value AS portfolio_value
                FROM holdings h
                JOIN portfolios p ON p.id = h.portfolio_id
                LEFT JOIN latest_quotes q ON q.security_id = h.security_id
                LEFT JOIN LATERAL (
                    SELECT close FROM price_history pp
                    WHERE pp.security_id = h.security_id
                    ORDER BY pp.trade_date DESC LIMIT 1
                ) ph ON TRUE
                LEFT JOIN LATERAL (
                    SELECT SUM(h2.shares * COALESCE(q2.price, ph2.close)) AS value
                    FROM holdings h2
                    LEFT JOIN latest_quotes q2 ON q2.security_id = h2.security_id
                    LEFT JOIN LATERAL (
                        SELECT close FROM price_history pp2
                        WHERE pp2.security_id = h2.security_id
                        ORDER BY pp2.trade_date DESC LIMIT 1
                    ) ph2 ON TRUE
                    WHERE h2.portfolio_id = h.portfolio_id
                ) totals ON TRUE
                WHERE p.user_id = :uid AND h.security_id = :sid
                ORDER BY p.name
                """
            ),
            {"uid": user.id, "sid": sec.id},
        )
    ).mappings().all()

    positions: list[PositionRow] = []
    for r in pos_rows:
        shares = int(r["shares"])
        avg_cost = Decimal(r["avg_cost_per_share"])
        cost_basis = int((avg_cost * shares).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        last_price = r["last_price"]
        market_value = shares * int(last_price) if last_price is not None else None
        pnl = market_value - cost_basis if market_value is not None else None
        positions.append(
            PositionRow(
                portfolio_id=r["portfolio_id"],
                portfolio_name=r["portfolio_name"],
                lots=shares // 100,
                shares=shares,
                avg_cost_per_share=float(round(avg_cost, 2)),
                cost_basis=cost_basis,
                market_value=market_value,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=(
                    round(pnl / cost_basis * 100, 2) if pnl is not None and cost_basis else None
                ),
                pct_of_portfolio=(
                    round(market_value / int(r["portfolio_value"]) * 100, 2)
                    if market_value is not None and r["portfolio_value"]
                    else None
                ),
            )
        )

    txn_rows = (
        await session.execute(
            sa_text(
                """
                SELECT t.executed_at, t.type, t.shares, t.price_per_share,
                       p.name AS portfolio_name
                FROM transactions t
                JOIN portfolios p ON p.id = t.portfolio_id
                WHERE p.user_id = :uid AND t.security_id = :sid
                ORDER BY t.executed_at
                """
            ),
            {"uid": user.id, "sid": sec.id},
        )
    ).mappings().all()

    return StockPositionOut(
        held=len(positions) > 0,
        positions=positions,
        transactions=[
            PositionTxn(
                executed_at=t["executed_at"],
                type=t["type"],
                lots=int(t["shares"]) // 100,
                price_per_share=t["price_per_share"],
                portfolio_name=t["portfolio_name"],
            )
            for t in txn_rows
        ],
    )
