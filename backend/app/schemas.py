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
