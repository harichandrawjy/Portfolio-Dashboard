# Arus — IDX Portfolio Dashboard

Track mock portfolios of Indonesian (IDX) stocks: record buy/sell
transactions in board lots, watch live value and time-weighted performance
against the IHSG benchmark, and drill into per-stock pages with five years
of history, risk analytics, and fundamentals.

Built as a personal portfolio project: FastAPI + PostgreSQL backend, React +
Vite + Tailwind frontend, Recharts for the portfolio curve and TradingView
Lightweight Charts for candles, Docker Compose for local dev.

## Screenshots

<!--
Capture at 1280px wide, light theme, with the demo portfolio seeded so the
figures are real. Save to docs/screenshots/ and delete the italic line below.

![Portfolio detail — value, allocation, holdings, ledger](docs/screenshots/portfolio-detail.png)
![Stock page — candles, your trades, break-even](docs/screenshots/stock-detail.png)
![Order entry — lots bounded by cash, IDX tick sizes](docs/screenshots/add-transaction.png)
-->

*Screenshots pending — the demo seed below gets you a populated app in a
couple of minutes.*

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
| Quote refresh | Mon–Fri 09:00–16:00, every 15 min | Delayed quotes for held tickers into `latest_quotes`, plus the session's OHLC so far for the in-progress candle |
| Fundamentals | Sat 06:00 | Market cap, P/E, EPS, yield, book value + curated extended stats (weekly — this data barely moves) |
| Statements | Sat 06:30 | Income statement, balance sheet, cash flow (≈4 annual, ≈5 quarters); solvency/efficiency metrics derived from them |
| Lazy backfill | on demand | 5y of daily OHLCV the first time anyone touches a ticker, then its stats, fundamentals, and statements immediately after |
| Startup catch-up | every boot | Replays what was missed while the machine was off: appends daily bars if they are behind the last published trading day, and refreshes quotes older than 30 minutes |

Those jobs only fire while the backend is running, so both containers use
`restart: unless-stopped` (a crashed watcher must not silently stop every
sync) and the app runs a catch-up on startup — see `app/sync/catchup.py`.
Nothing needs to be triggered by hand; the CLI commands remain available for
forcing a refresh.

Backend layout: `app/routers` (API), `app/sync` (all external data),
`app/analytics.py` (pure functions), `app/performance.py` (series builder),
`schema.sql` + Alembic migrations. Frontend: `src/api/client.ts` is the
single typed API surface; pages in `src/pages`, components in
`src/components`.

The interface follows a documented design system — one variable grotesk,
black rules and numbered sections instead of cards, and a single accent used
only as a full flat field. The contract, including the named rules and the
reasoning behind them, is in [`DESIGN.md`](DESIGN.md).

## Local setup

Prereqs: Docker Desktop, Node 20+.

```sh
cp .env.example .env                                   # defaults work for local dev
docker compose up -d --build                           # Postgres 16 + API :8000
docker compose exec backend alembic upgrade head       # create tables
docker compose exec backend python -m app.seed_demo    # demo template + 2y portfolio
cd frontend && npm install && npm run dev              # UI at :5173
```

Open <http://localhost:5173> and click **Explore the demo portfolio** — no
credentials needed. `POST /auth/demo` mints a private, throwaway account and
hands back a token, so every visitor gets their own copy of the seeded
portfolio and can buy, sell and delete in it without touching anyone else's.
Those accounts are rate-limited per caller and purged nightly once a day old.

The seed backfills real price history, so the first run needs network and
takes a minute or two. Re-running it is a no-op.

Tests: `docker compose exec backend pytest` (87 tests against a throwaway
database). CI runs them plus the frontend type-check/build on every push.

## Deployment

One box runs everything: Caddy for TLS and routing, the API, and Postgres,
with the built frontend served as static files from the same origin — which
is what keeps the client's `/api` prefix working without CORS. Steps,
configuration and the operational caveats are in [`DEPLOY.md`](DEPLOY.md).

## API summary

All endpoints except `/health` and `/auth/*` require a JWT bearer token.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/demo` (mints a throwaway account, no credentials), `GET /me` |
| Portfolios | `POST/GET /portfolios`, `GET/PATCH/DELETE /portfolios/{id}` — owner-scoped (others' portfolios 404) |
| Transactions | `POST/GET /portfolios/{id}/transactions` (lots in, shares stored), `PATCH/DELETE .../{txn_id}` with ledger-integrity guards |
| Cash | `GET/POST /portfolios/{id}/cash`, `DELETE .../cash/{flow_id}` — balance guarded so a delete cannot strand later buys |
| Analytics | `/portfolios/{id}/holdings`, `/performance?range=`, `/metrics?range=`, `/allocation` |
| Securities | `/securities/search?q=`, `/securities/{ticker}` (+`/prices`, `/position`, `/financials`, `/close`, `POST /ensure-prices`) |

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

**Performance methodology.** Everything reported is a time-weighted return,
so no movement of money can register as a gain — the chart plots cumulative
TWR against IHSG's own return over the same window, and its last point is
the total return the summary card states. It arrived there the long way: four
versions plotted rupiah, and each one fixed the previous artifact and
introduced its own (selling read as a loss, then funding read as a gain, then
same-day rotations counted twice). All four are written up in
`app/performance.py`, because the failure is instructive — a value line
answers "what is this worth", which moves when money moves, so a benchmark
laid over it compares an amount of money against an index. Sharpe uses Bank
Indonesia's policy rate from config as the risk-free assumption.

**Cash funds every buy.** Deposits and withdrawals live in `cash_flows` and
the balance is derived, never stored: deposits − withdrawals − buy costs
(incl. fees) + sell proceeds (net of fees). Every buy is checked against it,
so a new portfolio must record a deposit before it can trade, exactly like
funding a brokerage account; sells credit the balance back. Only trades on
or after the first cash flow count, so funding a portfolio that already has
history does not have its opening deposit drained by old buys. Analytics
still measure invested capital only — idle cash is a budgeting device, not
part of the performance series.

That exclusion needs a second rule to be safe, and finding out why was
instructive: **a buy may not be dated before the first cash flow.** The
affordability guards compute the balance with the same exclusion, so a buy
dated behind the funding was left out of the very sum meant to catch it and
cost nothing at all — deposit 94jt, buy 84jt dated earlier, and the balance
still reported the full 94jt. The same hole was reachable by editing an
affordable buy's date backwards. It is enforced on create and edit, for buys
only: a sell releases cash rather than spending it, and blocking it would
strand imported history.

**An unfinished session is never stored as a bar.** Yahoo returns the current
day as an ordinary row, so a sync during market hours used to write a partial
candle — and the startup catch-up, which compares dates, then saw a bar for
that date and concluded nothing was missing. One ticker sat on a mid-session
price of 565 whose real close was 615. `price_history` now refuses any bar
before the day's close is published; today's in-progress candle comes from
the quote cache instead, kept in `latest_quotes` and returned as a separate
`provisional` field so nothing that consumes the historical series can mistake
it for settled.

**Data licensing.** IDX's terms restrict commercial redistribution of
their data, and Yahoo Finance data comes with its own usage limits. This
is a personal, non-commercial project; a commercial version would use a
licensed market-data provider (e.g. an IDX data vendor) behind the same
sync interfaces.

## Roadmap (v2)

- US stocks and multi-currency portfolios (money model generalizes from
  whole-rupiah `BIGINT` to per-currency minor units; `.JK`-suffix handling
  becomes a per-exchange symbol map)
- Tax-lot accounting (realized P&L today is average-cost)
- Dividend tracking (cash flows would upgrade TWR handling too)
- Quotes for tickers nobody holds go stale after the first visit — the
  15-minute job only covers held tickers, so a browsed-but-unowned stock is
  fetched once and never refreshed

## Disclaimers

Mock portfolios only — nothing here executes real trades. Prices are
delayed and provided as-is for personal/educational use.
