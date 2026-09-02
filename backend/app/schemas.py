"""Pydantic request/response models."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    # bcrypt only reads the first 72 bytes; cap it so nothing is silently ignored
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = Field(default=None, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    created_at: datetime
    email_verified_at: datetime | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EmailIn(BaseModel):
    """Used by both `forgot password` and `resend verification`."""

    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class PasswordResetIn(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    # same floor and 72-byte ceiling as registration — bcrypt reads no further
    password: str = Field(min_length=8, max_length=72)


class AcceptedOut(BaseModel):
    """The deliberately uninformative reply to anything that takes an address.

    `/auth/password/forgot` and the verification resend both answer this way
    whether or not the account exists. Saying "no such user" would turn either
    into a membership oracle for any address someone cares to try.
    """

    detail: str = "If that address has an account, an email is on its way."


# ---------------------------------------------------------------------------
# Portfolios & transactions
# ---------------------------------------------------------------------------

class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class PortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class TransactionIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    type: Literal["BUY", "SELL"]
    lots: int = Field(ge=1, description="IDX board lots; 1 lot = 100 shares")
    price_per_share: int = Field(gt=0, description="whole rupiah")
    fee: int = Field(default=0, ge=0, description="whole rupiah")
    executed_at: date
    note: str | None = Field(default=None, max_length=500)


class TransactionUpdate(BaseModel):
    # ticker is fixed on edit (delete + re-add to change the security)
    type: Literal["BUY", "SELL"]
    lots: int = Field(ge=1)
    price_per_share: int = Field(gt=0)
    fee: int = Field(default=0, ge=0)
    executed_at: date
    note: str | None = Field(default=None, max_length=500)


class TransactionOut(BaseModel):
    id: uuid.UUID
    ticker: str
    type: Literal["BUY", "SELL"]
    lots: int
    shares: int
    price_per_share: int
    fee: int
    executed_at: date
    note: str | None
    created_at: datetime


class TransactionListOut(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


class HoldingOut(BaseModel):
    ticker: str
    name: str
    shares: int
    lots: int
    avg_cost_per_share: float
    cost_basis: int  # whole rupiah
    last_price: int | None  # delayed quote, else last close; None -> "—"
    market_value: int | None
    unrealized_pnl: int | None
    unrealized_pnl_pct: float | None
    realized_pnl: int  # locked in by past sells of this ticker (avg-cost)
    as_of: datetime | None  # quote timestamp; None when priced at a close
    last_close_date: date | None


class HoldingsTotals(BaseModel):
    cost_basis: int
    market_value: int | None
    unrealized_pnl: int | None
    # realized across ALL of the portfolio's sells, incl. fully-closed
    # positions that no longer appear in the holdings rows
    realized_pnl: int
    # cost basis of every share already sold. cost_basis covers open positions
    # only, so the two together are the capital committed to positions.
    realized_cost_basis: int
    # Deposits minus withdrawals: the money that actually entered from
    # outside. This is the total-return denominator, NOT the two above —
    # summing purchases counts recycled capital twice, so one round trip
    # roughly halves the reported percentage. Zero on a portfolio with no
    # cash ledger, where the caller falls back to committed capital.
    net_deposits: int
    unpriced_holdings: int  # how many holdings had no quote
    # cash ledger (0 / false until the portfolio's first deposit)
    cash_balance: int
    cash_tracked: bool
    # trades predating the first cash flow, which cash_balance ignores
    cash_uncounted_trades: int


class HoldingsOut(BaseModel):
    portfolio_id: uuid.UUID
    holdings: list[HoldingOut]
    totals: HoldingsTotals


# ---------------------------------------------------------------------------
# Cash ledger
# ---------------------------------------------------------------------------

class CashFlowIn(BaseModel):
    type: Literal["DEPOSIT", "WITHDRAW"]
    amount: int = Field(gt=0, description="whole rupiah")
    occurred_at: date | None = None  # defaults to today (WIB)
    note: str | None = Field(default=None, max_length=500)


class CashFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: Literal["DEPOSIT", "WITHDRAW"]
    amount: int
    occurred_at: date
    note: str | None


class CashSummaryOut(BaseModel):
    balance: int
    tracked: bool  # false until the first deposit/withdrawal
    flows: list[CashFlowOut]  # newest first, capped
    # trades dated before `first_flow_date` do not affect `balance`; the UI
    # says so rather than presenting cash those trades already spent
    uncounted_trades: int
    first_flow_date: date | None


# ---------------------------------------------------------------------------
# Performance & metrics
# ---------------------------------------------------------------------------

class PerformancePoint(BaseModel):
    """One day of the chart, as CUMULATIVE RETURN rather than rupiah.

    Both series start at 0.0 on the first point and are measured from it, so
    they overlay on one axis without either being rescaled to the other. The
    portfolio leg is time-weighted, which is what keeps deposits, sales and
    rotations off the line — see app/performance.py for the four rupiah
    versions of this chart that did not manage it.
    """

    date: date
    return_pct: float  # time-weighted, since the start of the window
    ihsg_return_pct: float | None


class PerformanceOut(BaseModel):
    portfolio_id: uuid.UUID
    range: str
    points: list[PerformancePoint]


class MetricsOut(BaseModel):
    portfolio_id: uuid.UUID
    range: str
    start_date: date | None
    end_date: date | None
    trading_days: int
    total_return_pct: float | None  # time-weighted (see app/performance.py)
    benchmark_return_pct: float | None
    annualized_volatility_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    beta: float | None
    risk_free_rate_pct: float


# ---------------------------------------------------------------------------
# Allocation & search
# ---------------------------------------------------------------------------

class StockSlice(BaseModel):
    ticker: str
    name: str
    sector: str | None
    market_value: int
    weight_pct: float


class SectorSlice(BaseModel):
    sector: str | None
    market_value: int
    weight_pct: float


class ConcentrationFlag(BaseModel):
    type: Literal["stock_concentration", "sector_concentration"]
    ticker: str | None = None
    sector: str | None = None
    weight_pct: float
    threshold_pct: float


class AllocationOut(BaseModel):
    portfolio_id: uuid.UUID
    total_market_value: int  # priced holdings only
    by_stock: list[StockSlice]
    by_sector: list[SectorSlice]
    flags: list[ConcentrationFlag]
    unpriced: list[str]  # held tickers with no price at all — excluded above


class FrontierPoint(BaseModel):
    """One allocation on the efficient frontier. Percentages, annualised."""

    volatility_pct: float
    expected_return_pct: float
    weights: dict[str, float]  # ticker -> percent, sums to 100


class Selection(BaseModel):
    """One named portfolio picked off the frontier.

    The textbook's three formulations are three ways of naming a point on the
    same curve, so all three are returned together and cannot disagree.
    """

    volatility_pct: float
    expected_return_pct: float
    sharpe: float | None  # (return - Rf) / volatility
    weights: dict[str, float]  # ticker -> percent


class AssetPoint(BaseModel):
    """A single holding plotted on the same axes as the frontier."""

    ticker: str
    volatility_pct: float
    expected_return_pct: float
    current_weight_pct: float  # what this portfolio actually holds today
    # Sensitivity to IHSG. Null when expected returns fell back to the
    # historical mean, which has no beta in it.
    beta: float | None


class FrontierOut(BaseModel):
    portfolio_id: uuid.UUID
    # Fewer than two priced holdings with overlapping history means there is
    # no frontier to draw — the UI says so rather than plotting a dot.
    curve: list[FrontierPoint]
    assets: list[AssetPoint]
    # Where the portfolio actually sits, on the same axes. Null when the
    # current holdings cannot be priced over the shared window.
    current_volatility_pct: float | None
    current_expected_return_pct: float | None
    trading_days: int  # observations behind the estimate — read it sceptically
    # The calendar year the estimate covers, and its bounds. Sent so the panel
    # can name the period instead of leaving "annualised" to be taken on faith.
    window_year: int
    window_start: date
    window_end: date
    excluded: list[str]  # held tickers dropped for want of overlapping history
    # How expected returns were estimated. "capm" uses Rf + B(Rm - Rf), which
    # is far steadier than a per-stock average; "historical" is the fallback
    # when IHSG lacks a bar on some date in the shared window.
    mu_source: Literal["capm", "log", "historical"]
    risk_free_rate_pct: float
    equity_risk_premium_pct: float
    # What CAPM assumes the market returns: risk-free + the premium above.
    market_return_pct: float | None
    # What IHSG actually did over this window. Shown beside the assumption so
    # the gap between them is visible rather than buried in a constant.
    market_return_realised_pct: float | None
    # The three formulations, all read off `curve`.
    min_risk: Selection | None
    max_sharpe: Selection | None
    # Present only when ?target_return_pct= was given AND is reachable.
    target: Selection | None
    # Bounds a caller can offer for the target input: below the floor is
    # already satisfied by minimum variance, above the ceiling is impossible
    # long-only.
    target_floor_pct: float | None
    target_ceiling_pct: float | None


class SecuritySearchOut(BaseModel):
    ticker: str
    name: str
    sector: str | None
    board: str | None
    last_price: int | None  # latest quote, else most recent close; entry aid


class EnsurePricesOut(BaseModel):
    # ready = prices already local; queued = backfill enqueued, poll search;
    # unavailable = background scheduler not running
    status: Literal["ready", "queued", "unavailable"]


# ---------------------------------------------------------------------------
# Stock detail
# ---------------------------------------------------------------------------

class SecurityStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    computed_at: datetime
    return_1d_pct: float | None
    return_1w_pct: float | None
    return_1mo_pct: float | None
    return_ytd_pct: float | None
    return_1y_pct: float | None
    return_5y_pct: float | None  # over stored history; backfill caps at ~5y
    high_52w: int | None
    low_52w: int | None
    high_all: int | None
    low_all: int | None
    avg_volume_3mo: int | None
    volatility_1y_pct: float | None
    max_drawdown_1y_pct: float | None
    beta_1y: float | None


class ExtraStats(BaseModel):
    """Curated extended stats (see sync/fundamentals whitelist). Monetary
    income/balance figures are denominated in financial_currency."""

    enterprise_value: int | None = None
    forward_pe: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    ev_to_revenue: float | None = None
    ev_to_ebitda: float | None = None
    peg_ratio: float | None = None
    earnings_yield_pct: float | None = None
    price_to_cashflow: float | None = None
    price_to_fcf: float | None = None
    profit_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    gross_margin_pct: float | None = None
    ebitda_margin_pct: float | None = None
    roa_pct: float | None = None
    roe_pct: float | None = None
    revenue_per_share: float | None = None
    cash_per_share: float | None = None
    fcf_per_share: float | None = None
    net_debt: int | None = None
    quick_ratio: float | None = None
    revenue: int | None = None
    revenue_growth_pct: float | None = None
    ebitda: int | None = None
    net_income: int | None = None
    earnings_growth_pct: float | None = None
    total_cash: int | None = None
    total_debt: int | None = None
    debt_to_equity_pct: float | None = None
    current_ratio: float | None = None
    operating_cash_flow: int | None = None
    free_cash_flow: int | None = None
    shares_outstanding: int | None = None
    float_shares: int | None = None
    held_insiders_pct: float | None = None
    held_institutions_pct: float | None = None
    avg_volume_10d: int | None = None
    forward_dividend_rate: float | None = None
    trailing_dividend_yield_pct: float | None = None
    five_year_avg_dividend_yield_pct: float | None = None
    payout_ratio_pct: float | None = None
    ex_dividend_date: date | None = None
    financial_currency: str | None = None


class FundamentalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_cap: int | None
    pe_ratio: float | None
    eps: float | None
    dividend_yield_pct: float | None
    book_value: float | None
    extra: ExtraStats | None
    last_updated: datetime


class SecurityDetailOut(BaseModel):
    ticker: str
    name: str
    sector: str | None
    board: str | None
    is_active: bool
    has_history: bool  # false -> frontend triggers ensure-prices and polls
    quote_price: int | None
    quote_change_pct: float | None
    quote_as_of: datetime | None
    # The session the quote belongs to, so a caller can tell a LIVE quote from
    # one left behind. Compare it with `last_close_date`: a quote is only
    # current while it is strictly newer than the last published bar. Equal
    # dates mean the bar has settled and the quote is the older of the two —
    # after the 18:30 bar job that is every held ticker at once.
    quote_trade_date: date | None
    last_close: int | None
    last_close_date: date | None
    stats: SecurityStatsOut | None  # null until the cache is computed
    fundamentals: FundamentalsOut | None  # null until the weekly sync ran


class StatementPeriodOut(BaseModel):
    period_end: date
    items: dict[str, float]  # whitelisted line items, reporting currency


class DerivedMetricsOut(BaseModel):
    """Computed from stored statements by app/sync/statements.py."""

    interest_coverage: float | None = None
    financial_leverage: float | None = None
    lt_debt_to_equity: float | None = None
    liabilities_to_equity: float | None = None
    debt_to_assets: float | None = None
    asset_turnover: float | None = None
    roce_pct: float | None = None
    days_sales_outstanding: float | None = None
    days_inventory: float | None = None
    days_payables: float | None = None
    cash_conversion_cycle: float | None = None
    fcf_ttm: float | None = None  # OCF - |capex|
    price_to_fcf_ttm: float | None = None
    altman_z: float | None = None  # emerging-markets Z''
    piotroski_f: int | None = None
    piotroski_max: int | None = None  # how many of the 9 signals were evaluable


class FinancialsOut(BaseModel):
    ticker: str
    currency: str | None  # issuer's reporting currency
    annual: list[StatementPeriodOut]  # newest first
    quarterly: list[StatementPeriodOut]  # newest first
    derived: DerivedMetricsOut


class CloseOnDateOut(BaseModel):
    """Closing price for a back-dated transaction. `trade_date` is the bar
    actually used, which may precede `requested` (weekends, holidays)."""

    ticker: str
    requested: date
    trade_date: date | None
    close: int | None


class StockPricePoint(BaseModel):
    date: date
    open: int | None
    high: int | None
    low: int | None
    close: int
    volume: int | None
    ihsg: int | None  # IHSG rebased to the stock's first close in range


class ProvisionalBar(BaseModel):
    """Today's session so far, from the quote cache — NOT a settled bar.

    Deliberately a separate field rather than the last element of `points`:
    everything that consumes `points` treats them as published closes, and one
    unfinished bar hiding among them is exactly the bug that froze a live price
    onto the chart. Present only while a session is genuinely in progress, so
    it disappears once the real bar is published that evening.
    """

    date: date
    open: int | None
    high: int | None
    low: int | None
    close: int
    volume: int | None
    as_of: datetime


class StockPricesOut(BaseModel):
    ticker: str
    range: str
    points: list[StockPricePoint]
    provisional: ProvisionalBar | None = None


class PositionRow(BaseModel):
    portfolio_id: uuid.UUID
    portfolio_name: str
    lots: int
    shares: int
    avg_cost_per_share: float
    cost_basis: int
    market_value: int | None
    unrealized_pnl: int | None
    unrealized_pnl_pct: float | None
    pct_of_portfolio: float | None


class PositionTxn(BaseModel):
    executed_at: date
    type: Literal["BUY", "SELL"]
    lots: int
    price_per_share: int
    portfolio_name: str


class StockPositionOut(BaseModel):
    held: bool
    positions: list[PositionRow]
    transactions: list[PositionTxn]  # chart markers
