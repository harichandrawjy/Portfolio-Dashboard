-- IDX Portfolio Dashboard — Postgres schema
-- Design principles:
--   1. Transactions are the source of truth; holdings are DERIVED, never stored.
--   2. All money is whole rupiah stored as BIGINT (IDX prices have no decimals).
--   3. Quantities stored in SHARES; the API layer converts lots <-> shares (1 lot = 100).
--   4. The IHSG benchmark (^JKSE) lives in the same securities table with kind='index'.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

-- ---------------------------------------------------------------------------
-- Users & auth
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Securities (IDX stocks + indices)
-- ---------------------------------------------------------------------------
CREATE TYPE security_kind AS ENUM ('stock', 'index');

CREATE TABLE securities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          TEXT NOT NULL UNIQUE,       -- 'BBCA', 'TLKM' (no .JK suffix; add it at the data-fetch layer)
    yahoo_symbol    TEXT NOT NULL UNIQUE,       -- 'BBCA.JK', '^JKSE'
    name            TEXT NOT NULL,              -- 'Bank Central Asia Tbk.'
    kind            security_kind NOT NULL DEFAULT 'stock',
    sector          TEXT,                       -- IDX-IC sector, e.g. 'Financials'
    board           TEXT,                       -- 'Main', 'Development', 'Acceleration'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at  TIMESTAMPTZ                 -- when prices were last refreshed (handle stale small caps)
);

CREATE INDEX idx_securities_ticker_search ON securities (ticker text_pattern_ops);

-- ---------------------------------------------------------------------------
-- Portfolios
-- ---------------------------------------------------------------------------
CREATE TABLE portfolios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

-- ---------------------------------------------------------------------------
-- Transactions — the source of truth
-- ---------------------------------------------------------------------------
CREATE TYPE txn_type AS ENUM ('BUY', 'SELL');

CREATE TABLE transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    security_id     UUID NOT NULL REFERENCES securities(id),
    type            txn_type NOT NULL,
    shares          INTEGER NOT NULL CHECK (shares > 0),
    -- IDX board lots are 100 shares; enforce it here, relax later if you add odd-lot support
    CONSTRAINT full_lots CHECK (shares % 100 = 0),
    price_per_share BIGINT  NOT NULL CHECK (price_per_share > 0),   -- whole IDR
    fee             BIGINT  NOT NULL DEFAULT 0 CHECK (fee >= 0),    -- broker fee in IDR
    executed_at     DATE    NOT NULL,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_txn_portfolio_date ON transactions (portfolio_id, executed_at);
CREATE INDEX idx_txn_security       ON transactions (security_id);

-- ---------------------------------------------------------------------------
-- Daily price history (also holds IHSG rows for benchmarking)
-- ---------------------------------------------------------------------------
CREATE TABLE price_history (
    security_id     UUID NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
    trade_date      DATE NOT NULL,
    open            BIGINT,
    high            BIGINT,
    low             BIGINT,
    close           BIGINT NOT NULL,
    volume          BIGINT,
    PRIMARY KEY (security_id, trade_date)
);

-- Fast "price series for a ticker over a range" lookups
CREATE INDEX idx_price_history_range ON price_history (security_id, trade_date DESC);

-- ---------------------------------------------------------------------------
-- Latest quote cache (refreshed by the scheduled job every ~15 min)
-- ---------------------------------------------------------------------------
CREATE TABLE latest_quotes (
    security_id     UUID PRIMARY KEY REFERENCES securities(id) ON DELETE CASCADE,
    price           BIGINT NOT NULL,
    change_pct      NUMERIC(8, 4),              -- vs previous close
    as_of           TIMESTAMPTZ NOT NULL,       -- quote timestamp from provider (delayed)
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Derived holdings view — current position per (portfolio, security)
-- ---------------------------------------------------------------------------
CREATE VIEW holdings AS
SELECT
    t.portfolio_id,
    t.security_id,
    SUM(CASE WHEN t.type = 'BUY' THEN t.shares ELSE -t.shares END)          AS shares,
    -- average cost basis over buys only (simple average-cost method)
    SUM(CASE WHEN t.type = 'BUY' THEN t.shares * t.price_per_share + t.fee ELSE 0 END)::NUMERIC
      / NULLIF(SUM(CASE WHEN t.type = 'BUY' THEN t.shares ELSE 0 END), 0)   AS avg_cost_per_share
FROM transactions t
GROUP BY t.portfolio_id, t.security_id
HAVING SUM(CASE WHEN t.type = 'BUY' THEN t.shares ELSE -t.shares END) > 0;
