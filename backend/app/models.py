"""ORM models mirroring schema.sql exactly — the SQL file is canonical.

The `holdings` view is intentionally not mapped here: it is derived state,
created by the initial migration and queried with explicit SQL when needed.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Types are created by the initial migration; create_type=False stops
# SQLAlchemy/Alembic from trying to re-create them.
security_kind = ENUM("stock", "index", name="security_kind", create_type=False)
txn_type = ENUM("BUY", "SELL", name="txn_type", create_type=False)
cash_flow_type = ENUM("DEPOSIT", "WITHDRAW", name="cash_flow_type", create_type=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Security(Base):
    __tablename__ = "securities"
    __table_args__ = (
        Index(
            "idx_securities_ticker_search",
            "ticker",
            postgresql_ops={"ticker": "text_pattern_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticker: Mapped[str] = mapped_column(Text, unique=True)
    yahoo_symbol: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(security_kind, server_default=text("'stock'"))
    sector: Mapped[str | None] = mapped_column(Text)
    board: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("shares > 0", name="transactions_shares_check"),
        CheckConstraint("shares % 100 = 0", name="full_lots"),
        CheckConstraint("price_per_share > 0", name="transactions_price_per_share_check"),
        CheckConstraint("fee >= 0", name="transactions_fee_check"),
        Index("idx_txn_portfolio_date", "portfolio_id", "executed_at"),
        Index("idx_txn_security", "security_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE")
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("securities.id")
    )
    type: Mapped[str] = mapped_column(txn_type)
    shares: Mapped[int] = mapped_column(Integer)
    price_per_share: Mapped[int] = mapped_column(BigInteger)
    fee: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    executed_at: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class CashFlow(Base):
    """Portfolio cash ledger entry (migration 0004). Balance is derived:
    deposits - withdrawals - buy costs + net sell proceeds."""

    __tablename__ = "cash_flows"
    __table_args__ = (
        CheckConstraint("amount > 0", name="cash_flows_amount_check"),
        Index("idx_cash_flows_portfolio", "portfolio_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(cash_flow_type)
    amount: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        Index("idx_price_history_range", "security_id", text("trade_date DESC")),
    )

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[int | None] = mapped_column(BigInteger)
    high: Mapped[int | None] = mapped_column(BigInteger)
    low: Mapped[int | None] = mapped_column(BigInteger)
    close: Mapped[int] = mapped_column(BigInteger)
    volume: Mapped[int | None] = mapped_column(BigInteger)


class SecurityStats(Base):
    """Nightly-computed stat cache; every value is derived from
    price_history and can be rebuilt at any time (migration 0002)."""

    __tablename__ = "security_stats"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    return_1d_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    return_1w_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    return_1mo_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    return_ytd_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    return_1y_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    return_5y_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    high_52w: Mapped[int | None] = mapped_column(BigInteger)
    low_52w: Mapped[int | None] = mapped_column(BigInteger)
    high_all: Mapped[int | None] = mapped_column(BigInteger)
    low_all: Mapped[int | None] = mapped_column(BigInteger)
    avg_volume_3mo: Mapped[int | None] = mapped_column(BigInteger)
    volatility_1y_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    max_drawdown_1y_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    beta_1y: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))


class Fundamentals(Base):
    """Weekly-refreshed Yahoo fundamentals; every value nullable because
    IDX coverage is patchy, especially for small caps (migration 0003)."""

    __tablename__ = "fundamentals"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    eps: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    dividend_yield_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    book_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    # curated extended stats (see app/sync/fundamentals.py whitelist)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class LatestQuote(Base):
    __tablename__ = "latest_quotes"

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("securities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    price: Mapped[int] = mapped_column(BigInteger)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    as_of: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
