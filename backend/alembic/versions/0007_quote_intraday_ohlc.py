"""Store today's in-progress OHLC alongside the latest quote.

`price_history` deliberately refuses to hold an unfinished session — a bar
written mid-session froze a live price as if it were a settled close (see
`prices._last_final_trade_date`). But the chart still needs to show today.

The quote job already downloads today's full bar every 15 minutes and keeps
only `Close`; these columns keep the rest. They live on `latest_quotes`
precisely because that table is a mutable latest-value cache — overwritten on
every refresh, never part of the historical series, and never read by
performance, TWR, or analytics. Nothing derived from `price_history` changes.

All nullable: an illiquid ticker can quote with no trades behind it, and rows
written before this migration have no values to backfill.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("latest_quotes", sa.Column("open", sa.BigInteger(), nullable=True))
    op.add_column("latest_quotes", sa.Column("high", sa.BigInteger(), nullable=True))
    op.add_column("latest_quotes", sa.Column("low", sa.BigInteger(), nullable=True))
    op.add_column("latest_quotes", sa.Column("volume", sa.BigInteger(), nullable=True))
    # The session the OHLC belongs to. Without it the API cannot tell a live
    # bar from yesterday's leftovers after the market closes, and would keep
    # drawing a stale provisional candle all evening.
    op.add_column("latest_quotes", sa.Column("trade_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("latest_quotes", "trade_date")
    op.drop_column("latest_quotes", "volume")
    op.drop_column("latest_quotes", "low")
    op.drop_column("latest_quotes", "high")
    op.drop_column("latest_quotes", "open")
