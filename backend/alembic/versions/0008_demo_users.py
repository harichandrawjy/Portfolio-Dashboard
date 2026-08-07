"""users.is_demo — mark the throwaway accounts minted by POST /auth/demo.

The demo used to be a single shared account whose credentials were compiled
into the JS bundle, so any visitor could delete the portfolio the next visitor
was about to look at. Each visitor now gets a private clone instead, which
means user rows accumulate and something has to know which of them are
disposable.

A column rather than an email-suffix convention. The purge job points a DELETE
at this table, and "rows whose address happens to look a certain way" is a
sharp thing to aim a DELETE with — a real user who picked an unlucky address
would be collateral. A boolean cannot be typed into a registration form.

The index is partial because the purge only ever scans demo rows and they are
the minority; on `created_at` because that is what the age cutoff compares.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "idx_users_demo_created",
        "users",
        ["created_at"],
        postgresql_where=sa.text("is_demo"),
    )


def downgrade() -> None:
    op.drop_index("idx_users_demo_created", table_name="users")
    op.drop_column("users", "is_demo")
