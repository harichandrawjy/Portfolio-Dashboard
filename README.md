# Arus — IDX Portfolio Dashboard

Track mock portfolios of Indonesian (IDX) stocks: record buy/sell
transactions in board lots, watch live value and time-weighted performance
against the IHSG benchmark, and drill into per-stock pages with five years
of history, risk analytics, and fundamentals.

Built as a personal portfolio project: FastAPI + PostgreSQL backend,
React + Vite + Tailwind + Recharts frontend, Docker Compose for local dev.

## Screenshots

<!-- TODO: add screenshots to docs/screenshots/ and uncomment
![Portfolio dashboard](docs/screenshots/dashboard.png)
![Stock detail](docs/screenshots/stock-detail.png)
![Add transaction](docs/screenshots/add-transaction.png)
-->
*Screenshots pending — run the demo seed below and see it live in under
five minutes.*

## Architecture

```
IDX website JSON  ──(nightly)──►  securities            ┐
  "what exists": tickers,          universe table       │
  names, sectors, boards                                │   FastAPI ──► React
                                                        ├──  reads         UI
yfinance          ──(jobs)────►  price_history          │   Postgres
  "what it's worth": OHLCV,       latest_quotes         │   only
  quotes, fundamentals            security_stats        │
                                  fundamentals          ┘
```

Two data sources with two distinct jobs, and one hard rule: **request
handlers never call an external API.** Everything the UI shows is served
from Postgres; background jobs (APScheduler, Asia/Jakarta clock) keep it
fresh:

| Job | Schedule | What it does |
|---|---|---|
| Universe sync | nightly 21:00 | IDX ticker list upsert; delistings deactivated, never deleted; CSV fallback if IDX is unreachable |
| Daily prices | Mon–Fri 18:30 | Appends recent bars for every tracked ticker + IHSG, then rebuilds the stat cache |
| Quote refresh | Mon–Fri 09:00–16:00, every 15 min | Delayed quotes for held tickers into `latest_quotes` |
| Fundamentals | Sat 06:00 | Market cap, P/E, EPS, yield, book value (weekly — this data barely moves) |
| Lazy backfill | on demand | 5y of daily OHLCV the first time anyone touches a ticker |

Backend layout: `app/routers` (API), `app/sync` (all external data),
`app/analytics.py` (pure functions), `app/performance.py` (series builder),
`schema.sql` + Alembic migrations. Frontend: `src/api/client.ts` is the
single typed API surface; pages in `src/pages`, components in
`src/components`.

## Local setup

Prereqs: Docker Desktop, Node 20+.

```sh
cp .env.example .env                                   # defaults work for local dev
docker compose up -d --build                           # Postgres 16 + API :8000
docker compose exec backend alembic upgrade head       # create tables
docker compose exec backend python -m app.seed_demo    # demo user + 2y portfolio
cd frontend && npm install && npm run dev              # UI at :5173
```

Sign in at <http://localhost:5173> with **demo@arus.id / arus-demo-123**.
The seed backfills real price history, so the first run needs network and
takes a minute or two. Re-running it is a no-op.

Tests: `docker compose exec backend pytest` (45 tests against a throwaway
database). CI runs them plus the frontend type-check/build on every push.

## API summary

All endpoints except `/health` and `/auth/*` require a JWT bearer token.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /me` |
| Portfolios | CRUD on `/portfolios`, owner-scoped (others' portfolios 404) |
| Transactions | `POST/GET /portfolios/{id}/transactions` (lots in, shares stored), `DELETE .../{txn_id}` |
| Analytics | `/portfolios/{id}/holdings`, `/performance?range=`, `/metrics?range=`, `/allocation` |
| Securities | `/securities/search?q=`, `/securities/{ticker}` (+`/prices`, `/position`, `POST /ensure-prices`) |

Interactive docs at `http://localhost:8000/docs`.

## Design decisions

**Transactions are the source of truth.** Holdings are a SQL view derived
from the transaction ledger — there is no stored position to drift out of
sync. Sells are validated against the view; deleting a buy that would
strand later sells is rejected.

**Integer rupiah, end to end.** IDX prices have no decimals, so every
money amount is a whole-rupiah `BIGINT` — no floats anywhere in the money
path. The frontend formats with `Intl.NumberFormat('id-ID')`.

**Lots at the edge, shares in the core.** Users enter IDX board lots
(1 lot = 100 shares); the API converts once at the boundary and a check
constraint (`shares % 100 = 0`) enforces it at the bottom.

**Lazy backfill instead of syncing ~900 tickers.** Backfilling the whole
exchange fights rate limits to store data nobody queries. A ticker gets
its 5 years of history the first time a user touches it; only tracked
tickers join the nightly incremental sync.

**Cache derived data, don't recompute it.** Quotes land in a small
`latest_quotes` table every 15 minutes during market hours. Per-ticker
statistics (window returns, 52w range, volatility, drawdown, beta) are
cached in `security_stats`, rebuilt nightly and immediately after a first
backfill — page reads are a primary-key lookup, and the analytics
functions themselves are pure and unit-tested with hand-computed values.

**Performance methodology.** The chart shows raw market value; metrics use
time-weighted returns so deposits never masquerade as gains (documented in
`app/performance.py`). Sharpe uses Bank Indonesia's policy rate from
config as the risk-free assumption.

**Data licensing.** IDX's terms restrict commercial redistribution of
their data, and Yahoo Finance data comes with its own usage limits. This
is a personal, non-commercial project; a commercial version would use a
licensed market-data provider (e.g. an IDX data vendor) behind the same
sync interfaces.

## Roadmap (v2)

- US stocks and multi-currency portfolios (money model generalizes from
  whole-rupiah `BIGINT` to per-currency minor units; `.JK`-suffix handling
  becomes a per-exchange symbol map)
- Realized P&L and tax-lot accounting
- Dividend tracking (cash flows would upgrade TWR handling too)

## Disclaimers

Mock portfolios only — nothing here executes real trades. Prices are
delayed and provided as-is for personal/educational use.
