"""financial_statements — whitelisted statement line items from Yahoo.

One row per (security, annual|quarterly, period_end); items is a JSONB of
normalized line items (floats, in the issuer's reporting currency).
Coverage: ~4 annual periods and ~5 quarters per ticker, patchy for small
caps. Purely derived data, rebuildable via python -m app.sync statements.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-19

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_statements",
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("securities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("period_type", sa.Text, primary_key=True),  # annual|quarterly
        sa.Column("period_end", sa.Date, primary_key=True),
        sa.Column("items", postgresql.JSONB, nullable=False),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("financial_statements")
