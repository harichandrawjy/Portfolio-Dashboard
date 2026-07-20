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


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    as_of: datetime | None  # quote timestamp; None when priced at a close
    last_close_date: date | None


class HoldingsTotals(BaseModel):
    cost_basis: int
    market_value: int | None
    unrealized_pnl: int | None
    unpriced_holdings: int  # how many holdings had no quote
    # cash ledger (0 / false until the portfolio's first deposit)
    cash_balance: int
    cash_tracked: bool


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


# ---------------------------------------------------------------------------
# Performance & metrics
# ---------------------------------------------------------------------------

class PerformancePoint(BaseModel):
    date: date
    portfolio_value: int  # whole rupiah
    ihsg_normalized: int | None  # IHSG rebased to the portfolio's start value


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
    profit_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    roa_pct: float | None = None
    roe_pct: float | None = None
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
    last_close: int | None
    last_close_date: date | None
    stats: SecurityStatsOut | None  # null until the cache is computed
    fundamentals: FundamentalsOut | None  # null until the weekly sync ran


class StockPricePoint(BaseModel):
    date: date
    open: int | None
    high: int | None
    low: int | None
    close: int
    volume: int | None
    ihsg: int | None  # IHSG rebased to the stock's first close in range


class StockPricesOut(BaseModel):
    ticker: str
    range: str
    points: list[StockPricePoint]


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
