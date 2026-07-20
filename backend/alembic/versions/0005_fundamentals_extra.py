"""fundamentals.extra — curated extended stats from Yahoo, as JSONB.

A whitelisted, normalized subset of Ticker.info (valuation ratios,
margins, balance-sheet figures, share stats, dividends). Display-only
ratios and foreign-currency financials, so JSONB floats are appropriate;
ledger money elsewhere stays BIGINT rupiah.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-19

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fundamentals", sa.Column("extra", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("fundamentals", "extra")
