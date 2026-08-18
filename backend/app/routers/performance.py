import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import text as sa_text

from app import analytics
from app.config import get_settings
from app.deps import CurrentUser, Session
from app.performance import (
    JAKARTA,
    RangeKey,
    aligned_benchmark_pairs,
    build_series,
    time_weighted_returns,
)
from app.optimize import covariance_matrix, efficient_frontier, portfolio_stats
from app.routers.portfolios import _get_owned_portfolio
from app.schemas import (
    AllocationOut,
    AssetPoint,
    ConcentrationFlag,
    FrontierOut,
    FrontierPoint,
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


# Two years of daily closes. Long enough that the covariance matrix is not
# pure noise, short enough that it still describes how these stocks behave
# now rather than how they behaved before a change of business.
FRONTIER_LOOKBACK_DAYS = 730

# Below this many overlapping observations the estimate is not worth drawing.
# Roughly a quarter of trading; the UI explains rather than plotting it.
MIN_OBSERVATIONS = 60


@router.get("/portfolios/{portfolio_id}/frontier", response_model=FrontierOut)
async def portfolio_frontier(
    portfolio_id: uuid.UUID, user: CurrentUser, session: Session
) -> FrontierOut:
    """Mean-variance frontier for what this portfolio holds.

    Answers "where does my allocation sit against the theoretically efficient
    ones", not "what should I buy". The distinction is deliberate: mean-variance
    weights are extremely sensitive to the expected-return estimate, which two
    years of daily data pins down badly, so a single recommended allocation
    would carry far more confidence than the inputs support. The curve, with
    the holdings scattered around it, shows the trade-off honestly.

    Every ticker is priced on ONE shared calendar. Covariance between series
    sampled on different days is meaningless, so a holding that did not trade
    across the shared window is excluded and named rather than silently
    interpolated.
    """
    portfolio = await _get_owned_portfolio(portfolio_id, user, session)

    rows = (
        await session.execute(
            sa_text(
                """
                SELECT s.ticker, h.shares
                  FROM holdings h
                  JOIN securities s ON s.id = h.security_id
                 WHERE h.portfolio_id = :pid
                 ORDER BY s.ticker
                """
            ),
            {"pid": portfolio.id},
        )
    ).all()
    held = {ticker: shares for ticker, shares in rows}
    cutoff = datetime.now(JAKARTA).date() - timedelta(days=FRONTIER_LOOKBACK_DAYS)

    closes: dict[str, dict] = {}
    if held:
        price_rows = (
            await session.execute(
                sa_text(
                    """
                    SELECT s.ticker, p.trade_date, p.close
                      FROM price_history p
                      JOIN securities s ON s.id = p.security_id
                     WHERE s.ticker = ANY(:tickers)
                       AND p.trade_date >= :cutoff
                     ORDER BY p.trade_date
                    """
                ),
                # Cutoff computed here rather than as `CURRENT_DATE - :days`:
                # asyncpg cannot infer the parameter's type inside that
                # expression and Postgres rejects it. Doing the arithmetic in
                # Python also keeps "today" on the app's Jakarta clock instead
                # of the database server's.
                {"tickers": list(held), "cutoff": cutoff},
            )
        ).all()
        for ticker, trade_date, close in price_rows:
            closes.setdefault(ticker, {})[trade_date] = close

    # The shared calendar: dates on which EVERY candidate traded.
    candidates = [t for t in held if len(closes.get(t, {})) >= MIN_OBSERVATIONS]
    common: set = set()
    for i, ticker in enumerate(candidates):
        dates = set(closes[ticker])
        common = dates if i == 0 else (common & dates)
    calendar = sorted(common)

    excluded = sorted(set(held) - set(candidates))
    if len(candidates) < 2 or len(calendar) < MIN_OBSERVATIONS:
        # One holding has no frontier; neither does a set that never overlaps.
        return FrontierOut(
            portfolio_id=portfolio.id,
            curve=[],
            assets=[],
            current_volatility_pct=None,
            current_expected_return_pct=None,
            trading_days=len(calendar),
            excluded=excluded if len(candidates) >= 2 else sorted(held),
        )

    returns = {
        ticker: analytics.daily_returns([closes[ticker][d] for d in calendar])
        for ticker in candidates
    }

    curve = efficient_frontier(returns)
    tickers, mu, cov = covariance_matrix(returns)

    # Today's actual weights, by market value at the newest shared close.
    last = calendar[-1]
    values = {t: held[t] * closes[t][last] for t in tickers}
    total = sum(values.values())
    current = [values[t] / total for t in tickers] if total else []

    current_return = current_vol = None
    if current:
        expected, vol = portfolio_stats(current, mu, cov)
        current_return, current_vol = expected * 100, vol * 100

    assets = [
        AssetPoint(
            ticker=t,
            # Diagonal of the covariance matrix is each asset's own variance.
            volatility_pct=float(cov[i][i] ** 0.5) * 100,
            expected_return_pct=float(mu[i]) * 100,
            current_weight_pct=(values[t] / total * 100) if total else 0.0,
        )
        for i, t in enumerate(tickers)
    ]

    return FrontierOut(
        portfolio_id=portfolio.id,
        curve=[
            FrontierPoint(
                volatility_pct=a.volatility * 100,
                expected_return_pct=a.expected_return * 100,
                weights={t: w * 100 for t, w in a.weights.items()},
            )
            for a in curve
        ],
        assets=assets,
        current_volatility_pct=current_vol,
        current_expected_return_pct=current_return,
        trading_days=len(calendar),
        excluded=excluded,
    )
