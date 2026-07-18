"""security_stats — nightly-computed per-ticker stat cache.

Purely derived data (recomputable from price_history at any time), so it
lives outside schema.sql's canonical design: dropping it loses nothing.
See README "Why security_stats exists" for the caching decision.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_stats",
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # simple returns, percent, 4dp; NULL = not enough history
        sa.Column("return_1d_pct", sa.Numeric(10, 4)),
        sa.Column("return_1w_pct", sa.Numeric(10, 4)),
        sa.Column("return_1mo_pct", sa.Numeric(10, 4)),
        sa.Column("return_ytd_pct", sa.Numeric(10, 4)),
        sa.Column("return_1y_pct", sa.Numeric(10, 4)),
        # over all stored history (the backfill window caps this at ~5y)
        sa.Column("return_5y_pct", sa.Numeric(10, 4)),
        # intraday basis where high/low exist, close otherwise; whole IDR
        sa.Column("high_52w", sa.BigInteger),
        sa.Column("low_52w", sa.BigInteger),
        sa.Column("high_all", sa.BigInteger),
        sa.Column("low_all", sa.BigInteger),
        sa.Column("avg_volume_3mo", sa.BigInteger),
        sa.Column("volatility_1y_pct", sa.Numeric(10, 4)),
        sa.Column("max_drawdown_1y_pct", sa.Numeric(10, 4)),
        sa.Column("beta_1y", sa.Numeric(10, 4)),
    )


def downgrade() -> None:
    op.drop_table("security_stats")
