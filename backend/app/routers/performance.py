import uuid
from collections import defaultdict
from datetime import date, datetime

import numpy as np

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
from app.optimize import (
    Allocation,
    annualised_log_mean,
    annualised_market_return,
    capm_expected_returns,
    covariance_matrix,
    efficient_frontier,
    frontier_tau_max,
    log_returns,
    portfolio_stats,
    select_for_target_return,
    select_max_sharpe,
    select_min_risk,
    sharpe_ratio_of,
)
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
    Selection,
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


# Four years of daily closes.
#
# Was two. Sigma is the half of this model the data estimates WELL, and it
# improves with observations — four years roughly doubles them where the
# history exists.
#
# The window is the last COMPLETE calendar year — 2025 while we are in 2026,
# 2026 once 2027 starts. A fixed year rather than a rolling lookback so the
# figures are quotable ("this is 2025") and stable: a rolling window silently
# re-estimates every night, so the same portfolio gives a different answer on
# consecutive days for no reason the reader can see.
#
# The trade-off is sample size. One year is ~240 sessions against ~950 for the
# old four-year window, and the standard error of a mean return scales as
# sigma/sqrt(T) — so halving sqrt(T) doubles it. Expected return was already
# the weak leg (see `equity_risk_premium` in config.py); on one year it is
# weaker still, which is one more reason CAPM rather than a per-stock average
# is the default. Risk and beta survive the cut better: both were the
# estimable half of the model to begin with.
def frontier_window(today: date | None = None) -> tuple[date, date, int]:
    """The last complete calendar year, on the app's Jakarta clock.

    Returns (first day, last day, year). Complete is the point: the current
    year is excluded however far into it we are, so the window never grows
    day by day.
    """
    now = today or datetime.now(JAKARTA).date()
    year = now.year - 1
    return date(year, 1, 1), date(year, 12, 31), year

# Below this many overlapping observations the estimate is not worth drawing.
# Roughly a quarter of trading; the UI explains rather than plotting it.
MIN_OBSERVATIONS = 60


@router.get("/portfolios/{portfolio_id}/frontier", response_model=FrontierOut)
async def portfolio_frontier(
    portfolio_id: uuid.UUID,
    user: CurrentUser,
    session: Session,
    mu_model: str = Query(
        default="capm",
        pattern="^(capm|log)$",
        description=(
            "How expected returns are estimated. 'capm' uses Rf + B(Rm - Rf), "
            "which is far steadier. 'log' uses each holding's own annualised "
            "log return — the geometric figure, so volatility drag is priced "
            "in, but still a historical estimate with a wide spread."
        ),
    ),
    target_return_pct: float | None = Query(
        default=None,
        description=(
            "Minimise risk subject to reaching this annualised return. Null "
            "in the response when unreachable long-only."
        ),
    ),
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
    window_start, window_end, window_year = frontier_window()

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
                       AND p.trade_date BETWEEN :start AND :end
                     ORDER BY p.trade_date
                    """
                ),
                # Bounds computed in Python, not as `CURRENT_DATE - :days`:
                # asyncpg cannot infer the parameter's type inside that
                # expression and Postgres rejects it. It also keeps "today" on
                # the app's Jakarta clock rather than the database server's.
                {"tickers": list(held), "start": window_start, "end": window_end},
            )
        ).all()
        for ticker, trade_date, close in price_rows:
            closes.setdefault(ticker, {})[trade_date] = close

    # IHSG is the market leg of CAPM, so it joins the shared calendar rather
    # than being matched against it afterwards. Betas compare two series day
    # by day; a benchmark sampled on even slightly different dates gives a
    # number that looks plausible and means nothing.
    ihsg_rows = (
        await session.execute(
            sa_text(
                """
                SELECT p.trade_date, p.close
                  FROM price_history p
                  JOIN securities s ON s.id = p.security_id
                 WHERE s.ticker = 'IHSG'
                   AND p.trade_date BETWEEN :start AND :end
                 ORDER BY p.trade_date
                """
            ),
            {"start": window_start, "end": window_end},
        )
    ).all()
    ihsg = {d: c for d, c in ihsg_rows}

    # The shared calendar: dates on which EVERY candidate traded.
    candidates = [t for t in held if len(closes.get(t, {})) >= MIN_OBSERVATIONS]
    common: set = set()
    for i, ticker in enumerate(candidates):
        dates = set(closes[ticker])
        common = dates if i == 0 else (common & dates)

    # Narrow to dates IHSG also has, but only if that leaves a usable window.
    # Yahoo occasionally has no ^JKSE bar on a day the constituents traded —
    # four such gaps in two years here. Dropping CAPM over a 1% shortfall
    # would trade a far better estimator for four observations, so intersect
    # and keep going; fall back only if the benchmark is genuinely unusable.
    with_market = common & set(ihsg)
    use_market = len(with_market) >= MIN_OBSERVATIONS and len(with_market) >= 0.8 * len(
        common
    )
    calendar = sorted(with_market if use_market else common)

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
            window_year=window_year,
            window_start=window_start,
            window_end=window_end,
            excluded=excluded if len(candidates) >= 2 else sorted(held),
            mu_source="historical",
            risk_free_rate_pct=get_settings().risk_free_rate_annual * 100,
            equity_risk_premium_pct=get_settings().equity_risk_premium * 100,
            market_return_pct=None,
            market_return_realised_pct=None,
            min_risk=None,
            max_sharpe=None,
            target=None,
            target_floor_pct=None,
            target_ceiling_pct=None,
        )

    returns = {
        ticker: analytics.daily_returns([closes[ticker][d] for d in calendar])
        for ticker in candidates
    }

    settings = get_settings()
    mu_source = "historical"
    # Log-return mu, if asked for. Sigma stays on SIMPLE returns whichever mu
    # is chosen: portfolio variance wᵀΣw is exact only when returns are
    # asset-additive, which log returns are not. Keeping the risk axis fixed
    # also makes the two models comparable — only the y-axis moves.
    log_mu = None
    if mu_model == "log":
        _, log_mu = annualised_log_mean(
            {
                ticker: log_returns([closes[ticker][d] for d in calendar])
                for ticker in candidates
            }
        )
        mu_source = "log"
    market_return = None
    market_realised = None
    betas: dict[str, float] = {}
    capm_mu = None  # stays None when the benchmark is unusable

    if use_market and mu_model == "capm":
        market_closes = [ihsg[d] for d in calendar]
        market_returns = analytics.daily_returns(market_closes)
        market_realised = annualised_market_return(market_closes)
        # E[Rm] is an ASSUMPTION, not the realised figure — see
        # config.equity_risk_premium for why. The realised number travels
        # alongside so the panel can show both.
        market_return = settings.risk_free_rate_annual + settings.equity_risk_premium
        _, capm_mu, capm_betas = capm_expected_returns(
            returns,
            market_returns,
            settings.risk_free_rate_annual,
            market_return,
        )
        mu_source = "capm"

    chosen_mu = capm_mu if mu_source == "capm" else log_mu
    curve = efficient_frontier(returns, mu=chosen_mu)
    tickers, hist_mu, cov = covariance_matrix(returns)
    mu = hist_mu if chosen_mu is None else np.asarray(chosen_mu, dtype=float)
    if mu_source == "capm":
        betas = {t: float(b) for t, b in zip(tickers, capm_betas)}

    # Today's actual weights, by market value at the newest shared close.
    last = calendar[-1]
    values = {t: held[t] * closes[t][last] for t in tickers}
    total = sum(values.values())
    current = [values[t] / total for t in tickers] if total else []

    current_return = current_vol = None
    if current:
        expected, vol = portfolio_stats(current, mu, cov)
        current_return, current_vol = expected * 100, vol * 100

    # The three formulations, read off the curve that is already computed.
    rf = settings.risk_free_rate_annual
    pick_min = select_min_risk(curve)
    pick_sharpe = select_max_sharpe(curve, mu, cov, tickers, rf)
    pick_target = (
        select_for_target_return(
            target_return_pct / 100, mu, cov, tickers, frontier_tau_max(mu, cov)
        )
        if target_return_pct is not None
        else None
    )

    assets = [
        AssetPoint(
            ticker=t,
            # Diagonal of the covariance matrix is each asset's own variance.
            volatility_pct=float(cov[i][i] ** 0.5) * 100,
            expected_return_pct=float(mu[i]) * 100,
            current_weight_pct=(values[t] / total * 100) if total else 0.0,
            beta=betas.get(t),
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
        window_year=window_year,
        window_start=window_start,
        window_end=window_end,
        excluded=excluded,
        min_risk=_selection(pick_min, settings.risk_free_rate_annual),
        max_sharpe=_selection(pick_sharpe, settings.risk_free_rate_annual),
        target=_selection(pick_target, settings.risk_free_rate_annual),
        target_floor_pct=None if pick_min is None else pick_min.expected_return * 100,
        target_ceiling_pct=(
            None if not curve else max(a.expected_return for a in curve) * 100
        ),
        mu_source=mu_source,
        risk_free_rate_pct=settings.risk_free_rate_annual * 100,
        equity_risk_premium_pct=settings.equity_risk_premium * 100,
        market_return_pct=None if market_return is None else market_return * 100,
        market_return_realised_pct=(
            None if market_realised is None else market_realised * 100
        ),
    )


def _selection(alloc: Allocation | None, risk_free_rate: float) -> Selection | None:
    """Allocation -> wire format, percentages."""
    if alloc is None:
        return None
    return Selection(
        volatility_pct=alloc.volatility * 100,
        expected_return_pct=alloc.expected_return * 100,
        sharpe=sharpe_ratio_of(alloc, risk_free_rate),
        weights={t: w * 100 for t, w in alloc.weights.items()},
    )
