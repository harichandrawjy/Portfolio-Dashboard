"""Initial schema — copied verbatim from schema.sql (project root).

schema.sql is the canonical design; this migration only splits it into
individual statements because asyncpg cannot execute multi-statement strings.

Revision ID: 0001
Revises:
Create Date: 2026-07-18

"""
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None

STATEMENTS: tuple[str, ...] = (
    'CREATE EXTENSION IF NOT EXISTS "pgcrypto"',
    """
    CREATE TABLE users (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email           TEXT NOT NULL UNIQUE,
        password_hash   TEXT NOT NULL,
        display_name    TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE TYPE security_kind AS ENUM ('stock', 'index')",
    """
    CREATE TABLE securities (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        ticker          TEXT NOT NULL UNIQUE,
        yahoo_symbol    TEXT NOT NULL UNIQUE,
        name            TEXT NOT NULL,
        kind            security_kind NOT NULL DEFAULT 'stock',
        sector          TEXT,
        board           TEXT,
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        last_synced_at  TIMESTAMPTZ
    )
    """,
    "CREATE INDEX idx_securities_ticker_search ON securities (ticker text_pattern_ops)",
    """
    CREATE TABLE portfolios (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name            TEXT NOT NULL,
        description     TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, name)
    )
    """,
    "CREATE TYPE txn_type AS ENUM ('BUY', 'SELL')",
    """
    CREATE TABLE transactions (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
        security_id     UUID NOT NULL REFERENCES securities(id),
        type            txn_type NOT NULL,
        shares          INTEGER NOT NULL CHECK (shares > 0),
        CONSTRAINT full_lots CHECK (shares % 100 = 0),
        price_per_share BIGINT  NOT NULL CHECK (price_per_share > 0),
        fee             BIGINT  NOT NULL DEFAULT 0 CHECK (fee >= 0),
        executed_at     DATE    NOT NULL,
        note            TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX idx_txn_portfolio_date ON transactions (portfolio_id, executed_at)",
    "CREATE INDEX idx_txn_security       ON transactions (security_id)",
    """
    CREATE TABLE price_history (
        security_id     UUID NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
        trade_date      DATE NOT NULL,
        open            BIGINT,
        high            BIGINT,
        low             BIGINT,
        close           BIGINT NOT NULL,
        volume          BIGINT,
        PRIMARY KEY (security_id, trade_date)
    )
    """,
    "CREATE INDEX idx_price_history_range ON price_history (security_id, trade_date DESC)",
    """
    CREATE TABLE latest_quotes (
        security_id     UUID PRIMARY KEY REFERENCES securities(id) ON DELETE CASCADE,
        price           BIGINT NOT NULL,
        change_pct      NUMERIC(8, 4),
        as_of           TIMESTAMPTZ NOT NULL,
        fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE VIEW holdings AS
    SELECT
        t.portfolio_id,
        t.security_id,
        SUM(CASE WHEN t.type = 'BUY' THEN t.shares ELSE -t.shares END)          AS shares,
        SUM(CASE WHEN t.type = 'BUY' THEN t.shares * t.price_per_share + t.fee ELSE 0 END)::NUMERIC
          / NULLIF(SUM(CASE WHEN t.type = 'BUY' THEN t.shares ELSE 0 END), 0)   AS avg_cost_per_share
    FROM transactions t
    GROUP BY t.portfolio_id, t.security_id
    HAVING SUM(CASE WHEN t.type = 'BUY' THEN t.shares ELSE -t.shares END) > 0
    """,
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in (
        "DROP VIEW holdings",
        "DROP TABLE latest_quotes",
        "DROP TABLE price_history",
        "DROP TABLE transactions",
        "DROP TABLE portfolios",
        "DROP TABLE securities",
        "DROP TABLE users",
        "DROP TYPE txn_type",
        "DROP TYPE security_kind",
    ):
        op.execute(statement)
