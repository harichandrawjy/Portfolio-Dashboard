"""cash_flows — portfolio cash ledger (deposits and withdrawals).

Cash balance is DERIVED, never stored: deposits - withdrawals - buy costs
(incl. fees) + sell proceeds (net of fees). Portfolios with no cash flows
keep the original untracked-cash behavior; the first deposit opts in.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgresql.ENUM("DEPOSIT", "WITHDRAW", name="cash_flow_type").create(
        op.get_bind(), checkfirst=True
    )
    # create_type=False: the type was created above; without it create_table
    # would try to CREATE TYPE a second time and fail
    cash_flow_type = postgresql.ENUM(
        "DEPOSIT", "WITHDRAW", name="cash_flow_type", create_type=False
    )
    op.create_table(
        "cash_flows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", cash_flow_type, nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),  # whole IDR
        sa.Column("occurred_at", sa.Date, nullable=False),
        sa.Column("note", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount > 0", name="cash_flows_amount_check"),
    )
    op.create_index(
        "idx_cash_flows_portfolio", "cash_flows", ["portfolio_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("cash_flows")
    postgresql.ENUM(name="cash_flow_type").drop(op.get_bind())
