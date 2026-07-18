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
    last_price: int | None  # None -> frontend renders "—"
    market_value: int | None
    unrealized_pnl: int | None
    unrealized_pnl_pct: float | None
    as_of: datetime | None


class HoldingsTotals(BaseModel):
    cost_basis: int
    market_value: int | None
    unrealized_pnl: int | None
    unpriced_holdings: int  # how many holdings had no quote


class HoldingsOut(BaseModel):
    portfolio_id: uuid.UUID
    holdings: list[HoldingOut]
    totals: HoldingsTotals


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
