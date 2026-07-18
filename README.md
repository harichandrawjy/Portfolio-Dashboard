# IDX Portfolio Dashboard

Mock-portfolio tracker for Indonesian (IDX) stocks — record buy/sell transactions,
track portfolio value and performance vs the IHSG benchmark (`^JKSE`), and view
risk analytics and per-stock detail pages.

## Stack

- **Backend** — FastAPI (Python 3.12), SQLAlchemy 2.0 + asyncpg, Alembic, PostgreSQL 16
- **Frontend** — React + Vite + Tailwind, Recharts *(scaffolded in a later step)*
- **Local dev** — Docker Compose

## Quickstart

```sh
cp .env.example .env          # adjust if you like; defaults work for local dev
docker compose up --build
docker compose exec backend alembic upgrade head   # in another terminal
```

- API: <http://localhost:8000> — health at `/health`, OpenAPI docs at `/docs`
- Postgres: `localhost:5432` (`app` / `portfolio` by default)

## Layout

```
backend/     FastAPI app + Alembic migrations
frontend/    React app (later step)
schema.sql   Canonical database schema — source of the initial migration
```

## Data sync

```sh
docker compose exec backend python -m app.sync universe                # refresh IDX ticker universe
docker compose exec backend python -m app.sync backfill --ticker BBCA  # 5y OHLCV history (repeatable flag)
docker compose exec backend python -m app.sync daily                   # append recent bars for tracked tickers
docker compose exec backend python -m app.sync quotes                  # refresh latest_quotes (held + ^JKSE)
```

Scheduled jobs (APScheduler, Asia/Jakarta): universe nightly 21:00; daily
prices Mon–Fri 18:30; quotes every 15 min Mon–Fri 09:00–16:00. Price history
is backfilled lazily — a ticker gets 5 years of daily bars the first time a
portfolio needs it, not before. If IDX is unreachable the universe sync falls
back to the bundled snapshot `backend/app/data/idx_universe.csv` (insert-only —
it can seed a fresh database but never overwrites or deactivates existing rows).

## Why security_stats exists

The stock detail page shows ~12 statistics (window returns, 52-week range,
average volume, volatility, drawdown, beta) derived from up to ~1,250 daily
bars per ticker. Computing those on every page load would rescan
price_history per request for numbers that change once a day. Instead they
are cached in the `security_stats` table (migration 0002) and recomputed by
the nightly price job, plus once immediately after a ticker's first-use
backfill, so a first visit shows stats within seconds. Page reads are a
single primary-key lookup. The table is purely derived state: dropping it
loses nothing that `python -m app.sync stats` cannot rebuild.

## Design notes

- Transactions are the source of truth; holdings are a derived SQL view.
- All money is whole-rupiah `BIGINT` — no floats anywhere.
- Quantities are stored in shares; the API converts IDX lots (1 lot = 100 shares).
- External data (IDX metadata, yfinance prices) is only ever fetched by background
  jobs and served from Postgres — never from a request handler.
