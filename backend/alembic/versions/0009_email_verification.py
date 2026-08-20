"""Email verification and password reset.

Three things, all in service of one feature.

`users.email_verified_at` is a timestamp rather than a boolean because
"when" answers questions "whether" cannot — whether a stale account predates
a policy change, whether a support request is plausible. NULL means
unverified, which makes the check a NULL test rather than a default-false
column that silently reads as "unverified" if a backfill is missed.

Existing rows are grandfathered as verified. Mandatory verification applied
retroactively would lock every current account out of its own portfolios,
including the operator's, with the only recovery path being the very email
system being deployed. Demo rows are deliberately left NULL: their addresses
are synthetic, "verified" would be a lie, and the login gate bypasses them on
`is_demo` anyway.

`users.token_version` exists because the JWTs here are stateless. A reset
that does not invalidate outstanding tokens is theatre — the attacker whose
access prompted the reset keeps it until the token expires on its own, which
is the one moment the feature is supposed to protect against. Every token
carries the version it was minted under, and `get_current_user` refuses any
that disagrees with the column.

A counter, not a `password_changed_at` timestamp, and that was a correction
rather than a first instinct. `iat` is stored as whole seconds, so a
timestamp comparison cannot order two events inside the same second — and the
reset endpoint mints a replacement token in exactly that window. Slack wide
enough to keep the new token valid is slack wide enough to keep the old one
valid too, which is the entire hole. An integer has no granularity to lose.

Tokens issued before this migration carry no version claim and are refused,
so everyone signs in once more after it lands. That is the safe direction:
the alternative is a claim that defaults to valid when absent.

`auth_tokens` stores a SHA-256 of the token, never the token. A reset link is
a bearer credential for the account: a database leak that hands over live
reset links is barely better than one that hands over passwords. SHA-256
rather than bcrypt because these are 256-bit random values, not
human-memorable secrets — there is no dictionary to slow down, and a reset
endpoint that costs 100ms of KDF per attempt is a free denial-of-service.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Grandfather real accounts; leave demo rows NULL (see docstring).
    op.execute(
        "UPDATE users SET email_verified_at = now() WHERE NOT is_demo"
    )
    op.create_table(
        "auth_tokens",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 'verify' | 'reset'. Text plus a CHECK rather than a PG enum: adding a
        # value to an enum needs its own migration, and this is exactly the
        # kind of list that grows (email change, invite).
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        # Set on redemption. A column rather than a DELETE so a second click on
        # the same link is distinguishable from a link that never existed.
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("kind IN ('verify', 'reset')", name="ck_auth_tokens_kind"),
    )
    # Issuing a token retires the holder's earlier unused ones of the same
    # kind, so this pair is the hot path, not the primary key.
    op.create_index(
        "idx_auth_tokens_user_kind", "auth_tokens", ["user_id", "kind"]
    )


def downgrade() -> None:
    op.drop_index("idx_auth_tokens_user_kind", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_column("users", "token_version")
    op.drop_column("users", "email_verified_at")
