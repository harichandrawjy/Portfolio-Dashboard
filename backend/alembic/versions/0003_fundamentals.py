"""fundamentals — weekly-refreshed per-ticker fundamentals from Yahoo.

Yahoo's IDX coverage is patchy (small caps often miss fields entirely),
so every value column is nullable and the row carries its own
last_updated. Purely derived data, rebuildable at any time.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fundamentals",
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("market_cap", sa.BigInteger),          # whole IDR
        sa.Column("pe_ratio", sa.Numeric(12, 4)),        # trailing P/E
        sa.Column("eps", sa.Numeric(14, 4)),             # IDR/share, can be negative
        sa.Column("dividend_yield_pct", sa.Numeric(8, 4)),
        sa.Column("book_value", sa.Numeric(14, 4)),      # IDR/share
        sa.Column(
            "last_updated",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("fundamentals")
