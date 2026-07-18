import uuid
from collections import defaultdict

from fastapi import APIRouter, Query
from sqlalchemy import text as sa_text

from app import analytics
from app.config import get_settings
from app.deps import CurrentUser, Session
from app.performance import (
    RangeKey,
    aligned_benchmark_pairs,
    build_series,
    time_weighted_returns,
)
from app.routers.portfolios import _get_owned_portfolio
from app.schemas import (
    AllocationOut,
    ConcentrationFlag,
    MetricsOut,
    PerformanceOut,
    PerformancePoint,
    SectorSlice,
    StockSlice,
)

router = APIRouter(tags=["performance"])

STOCK_CONCENTRATION_THRESHOLD_PCT = 30.0
SECTOR_CONCENTRATION_THRESHOLD_PCT = 50.0


@router.get("/portfolios/{portfolio_id}/performance", response_model=PerformanceOut)
async def portfolio_performance(
    portfolio_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
    range_key: RangeKey = Query(default="1y", alias="range"),
) -> PerformanceOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    points = await build_series(session, portfolio.id, range_key)

    out: list[PerformancePoint] = []
    if points:
        v0 = points[0].value
        i0 = points[0].ihsg_close
        for p in points:
            normalized = None
            if p.ihsg_close and i0:
                # Rebase IHSG to the portfolio's starting value so both
                # series overlay on one chart axis.
                normalized = round(p.ihsg_close / i0 * v0)
            out.append(
                PerformancePoint(
                    date=p.date, portfolio_value=p.value, ihsg_normalized=normalized
                )
            )

    return PerformanceOut(portfolio_id=portfolio.id, range=range_key, points=out)


@router.get("/portfolios/{portfolio_id}/metrics", response_model=MetricsOut)
async def portfolio_metrics(
    portfolio_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
    range_key: RangeKey = Query(default="1y", alias="range"),
) -> MetricsOut:
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)
    settings = get_settings()
    points = await build_series(session, portfolio.id, range_key)

    empty = MetricsOut(
        portfolio_id=portfolio.id,
        range=range_key,
        start_date=points[0].date if points else None,
        end_date=points[-1].date if points else None,
        trading_days=len(points),
        total_return_pct=None,
        benchmark_return_pct=None,
        annualized_volatility_pct=None,
        sharpe_ratio=None,
        max_drawdown_pct=None,
        beta=None,
        risk_free_rate_pct=round(settings.risk_free_rate_annual * 100, 2),
    )
    if len(points) < 2:
        return empty

    twr = time_weighted_returns(points)
    if not twr:
        return empty

    # Chain daily TWRs into a growth-of-1 index; total return and drawdown
    # both come from this index so cash flows never masquerade as gains.
    index = [1.0]
    for r in twr:
        index.append(index[-1] * (1 + r))
    total_return = index[-1] - 1

    volatility = analytics.annualized_volatility(twr)
    sharpe = analytics.sharpe_ratio(twr, settings.risk_free_rate_annual)
    drawdown = analytics.max_drawdown(index)

    port_aligned, bench_aligned = aligned_benchmark_pairs(points)
    beta = analytics.beta(port_aligned, bench_aligned)

    bench_levels = [p.ihsg_close for p in points if p.ihsg_close]
    bench_return = analytics.simple_return(bench_levels)

    def pct(x: float | None) -> float | None:
        return None if x is None else round(x * 100, 2)

    return empty.model_copy(
        update={
            "total_return_pct": pct(total_return),
            "benchmark_return_pct": pct(bench_return),
            "annualized_volatility_pct": pct(volatility),
            "sharpe_ratio": None if sharpe is None else round(sharpe, 2),
            "max_drawdown_pct": pct(drawdown),
            "beta": None if beta is None else round(beta, 3),
        }
    )


@router.get("/portfolios/{portfolio_id}/allocation", response_model=AllocationOut)
async def portfolio_allocation(
    portfolio_id: uuid.UUID, user: CurrentUser, session: Session
) -> AllocationOut:
    """Sector/stock breakdown by market value, with concentration flags.

    Price per holding: the latest quote, falling back to the most recent
    stored close. Holdings with neither are listed in `unpriced` and
    excluded from the weights (a weight against an unknown value would
    be a lie).
    """
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)

    rows = await session.execute(
        sa_text(
            """
            SELECT s.ticker, s.name, s.sector, h.shares,
                   COALESCE(q.price, ph.close) AS price
            FROM holdings h
            JOIN securities s ON s.id = h.security_id
            LEFT JOIN latest_quotes q ON q.security_id = h.security_id
            LEFT JOIN LATERAL (
                SELECT close FROM price_history p
                WHERE p.security_id = h.security_id
                ORDER BY p.trade_date DESC LIMIT 1
            ) ph ON TRUE
            WHERE h.portfolio_id = :pid
            """
        ),
        {"pid": portfolio.id},
    )

    priced: list[tuple[str, str, str | None, int]] = []  # ticker, name, sector, mv
    unpriced: list[str] = []
    for r in rows.mappings():
        if r["price"] is None:
            unpriced.append(r["ticker"])
        else:
            priced.append(
                (r["ticker"], r["name"], r["sector"], int(r["shares"]) * int(r["price"]))
            )

    total = sum(mv for *_, mv in priced)

    by_stock: list[StockSlice] = []
    sector_totals: dict[str | None, int] = defaultdict(int)
    for ticker, name, sector, mv in sorted(priced, key=lambda x: (-x[3], x[0])):
        by_stock.append(
            StockSlice(
                ticker=ticker,
                name=name,
                sector=sector,
                market_value=mv,
                weight_pct=round(mv / total * 100, 2) if total else 0.0,
            )
        )
        sector_totals[sector] += mv

    by_sector = [
        SectorSlice(
            sector=sector,
            market_value=mv,
            weight_pct=round(mv / total * 100, 2) if total else 0.0,
        )
        for sector, mv in sorted(
            sector_totals.items(), key=lambda x: (-x[1], x[0] or "")
        )
    ]

    flags: list[ConcentrationFlag] = [
        ConcentrationFlag(
            type="stock_concentration",
            ticker=s.ticker,
            weight_pct=s.weight_pct,
            threshold_pct=STOCK_CONCENTRATION_THRESHOLD_PCT,
        )
        for s in by_stock
        if s.weight_pct > STOCK_CONCENTRATION_THRESHOLD_PCT
    ] + [
        ConcentrationFlag(
            type="sector_concentration",
            sector=s.sector,
            weight_pct=s.weight_pct,
            threshold_pct=SECTOR_CONCENTRATION_THRESHOLD_PCT,
        )
        for s in by_sector
        if s.weight_pct > SECTOR_CONCENTRATION_THRESHOLD_PCT
    ]

    return AllocationOut(
        portfolio_id=portfolio.id,
        total_market_value=total,
        by_stock=by_stock,
        by_sector=by_sector,
        flags=flags,
        unpriced=sorted(unpriced),
    )
