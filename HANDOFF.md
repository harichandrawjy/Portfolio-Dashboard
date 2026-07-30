# Arus — project handoff

Context for picking this project up in a fresh session. Read this plus
`README.md`; the frontend design contract lives in Claude memory
(`frontend-design-direction`) and in `.claude/skills`.

## What it is

**Arus** — a mock-portfolio tracker for Indonesian (IDX) stocks, built as a CS
student portfolio project. Users create portfolios, fund them with cash,
record buy/sell transactions in board lots, and see live value,
time-weighted performance vs the IHSG benchmark, risk analytics, allocation,
and per-stock detail pages with fundamentals and financial statements.

Personal / non-commercial. Nothing executes real trades.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0 async + asyncpg, Alembic, APScheduler |
| Database | PostgreSQL 16 |
| Frontend | React 19 + Vite + TypeScript + Tailwind v4 |
| Charts | Recharts (portfolio/donut) + TradingView Lightweight Charts (stock candles) |
| Dev | Docker Compose (db + backend); Vite dev server run separately on the host |
| CI | GitHub Actions: pytest against a Postgres service + frontend tsc/build |

## Repository layout

```
schema.sql                  canonical DB design (migration 0001 mirrors it verbatim)
docker-compose.yml          postgres + backend, both restart: unless-stopped
.github/workflows/ci.yml
.claude/launch.json         dev-server config for the preview tool (autoPort: true)
backend/
  app/
    main.py                 app factory, lifespan (scheduler + startup catch-up)
    config.py               pydantic-settings; DATABASE_URL, SECRET_KEY, BI rate
    models.py               ORM models
    schemas.py              all Pydantic request/response models
    security.py deps.py     bcrypt + JWT, CurrentUser dependency
    analytics.py            PURE functions: returns, volatility, Sharpe, drawdown, beta
    performance.py          daily valuation series (replays transactions), TWR
    pnl.py                  PURE realized P&L (average-cost)
    scheduler.py            APScheduler jobs + enqueue_backfill()
    seed_demo.py            one-command demo seed
    routers/                auth, portfolios, performance, securities, health
    sync/                   ALL external data: idx, prices, stats, fundamentals,
                            statements, universe, catchup, __main__ (CLI)
    data/idx_universe.csv   963-ticker offline fallback snapshot
  alembic/versions/         0001..0006
  tests/                    12 test files, 79 tests
frontend/
  src/api/client.ts         THE single typed API surface (no fetch elsewhere)
  src/colors.ts             dataviz-validated chart palette
  src/styles.css            Tailwind v4 @theme design tokens
  src/pages/                Login, Portfolios, PortfolioDetail, Stock
  src/components/           ui.tsx (Panel/Button/Modal/ConfirmDialog/...), charts, modals
  src/lib/                  format.ts (id-ID money/dates), hooks.ts (useAsync)
```

## Load-bearing architecture decisions

Do not casually undo these — each was deliberate.

1. **Transactions are the source of truth.** Holdings are a derived SQL view
   (`holdings`), never stored. Cash balance is likewise derived, never stored.
2. **All money is whole-rupiah `BIGINT`** end to end. No floats in the money
   path. Frontend formats with `Intl.NumberFormat('id-ID')`.
3. **Lots at the edge, shares in the core.** Users enter board lots (1 lot =
   100 shares); the API converts once, and a check constraint enforces
   `shares % 100 = 0`.
4. **Request handlers never call an external API.** Everything is served from
   Postgres; `app/sync/*` background jobs are the only things that touch
   IDX/Yahoo.
5. **Two data sources, two jobs.** IDX website JSON answers *which stocks
   exist* (nightly, whole universe, cheap single request). yfinance answers
   *what they are worth* (lazy, per ticker, expensive).
6. **Lazy price backfill, not blanket sync.** A ticker gets 5 years of daily
   bars the first time anyone touches it (buy, or opening its stock page),
   then its stats/fundamentals/statements immediately after. Only tickers
   with history join the nightly incremental. This is why market-wide
   features (rank percentiles, IHSG median P/E, relative strength) are NOT
   feasible without reversing the design.
7. **Derived data is cached, pure logic is not.** `security_stats` (nightly)
   and `fundamentals`/`financial_statements` (weekly) are caches; the
   analytics/pnl/statement-derivation functions are pure and unit-tested with
   hand-computed values.
8. **TWR for metrics, raw value for the chart.** Documented in
   `performance.py`: trades count as external cash flows so deposits never
   masquerade as gains.
9. **Cash funds every buy.** Buys are always validated against the derived
   balance, so a new portfolio must deposit before trading. Only trades on or
   after the first cash flow count, so funding a portfolio that already has
   history is not drained by old buys.
10. **Frontend design must not read as a generic AI dashboard.** Light-only
    ("Arus / Broadsheet": cool porcelain + ink-indigo). The user rejected dark
    fintech twice. See the memory file before touching styling.

## Scheduled jobs (Asia/Jakarta)

| Job | When |
|---|---|
| Universe sync | nightly 21:00 |
| Daily bars | Mon–Fri 18:30 (then rebuilds the stat cache) |
| Quote refresh | Mon–Fri 09:00–16:00, every 15 min |
| Fundamentals | Sat 06:00 |
| Statements | Sat 06:30 |
| Startup catch-up | every boot — appends missed bars, refreshes quotes >30 min old |

Jobs only run while containers are up, hence `restart: unless-stopped` plus
the catch-up. Manual override: `docker compose exec backend python -m app.sync
<universe|backfill|daily|quotes|stats|fundamentals|statements>`.

## Done (39 commits, all 11 original build steps + extras)

**Steps 1–11 (the original plan), all verified:** scaffold/Docker/Alembic ·
IDX universe sync with CSV fallback · yfinance lazy backfill + nightly +
quotes · auth (bcrypt + JWT) · portfolios/transactions/holdings · analytics
engine (pure functions + performance/metrics endpoints) · allocation +
concentration flags + universe search · React frontend · stock detail page
with cached stats · weekly fundamentals · CI + README + one-command demo seed.

**Added since, on user request:**
- Cash ledger: deposits/withdrawals, derived balance, delete with balance
  guard; **buying now requires cash**
- Broker-style order entry: lots slider bounded by cash (buy) / holdings
  (sell), IDX tick-size steppers, percentage fees (Stockbit 0.15% / 0.25%),
  thousands-dot inputs, price prefill (last price, or **that date's close for
  back-dated trades**)
- Sell mode lists only what the portfolio holds
- Edit + delete transactions (with ledger-integrity guards); delete portfolio
  with confirmation
- Realized P&L (average-cost, includes closed positions) + per-row Buy/Sell
- TradingView Lightweight Charts for stock candles, with candles/line toggle
- Extended fundamentals (~30 curated Yahoo fields, currency-guarded) and
  **Tier-2 financial statements** with derived solvency/efficiency metrics,
  Altman Z'', Piotroski F
- Global masthead search with `/` shortcut + recent tickers
- Two UI redesigns → current light "Arus / Broadsheet" system
- Automatic refresh: restart policy + startup catch-up
- **Data-quality fixes**: full company names (IDX's stock-list endpoint
  truncates at 30 chars; the profiles endpoint has the real one — 905 of 963
  names corrected), and back-adjustment of corporate actions Yahoo never
  recorded (`adjust_corporate_actions` in `sync/prices.py`)

**Test suite: 79 passing.** `docker compose exec backend pytest`

## Not done / known gaps

- **Never pushed to GitHub.** No remote configured; CI has never run. This is
  the single biggest remaining task for a portfolio project.
- **No screenshots** in the README (placeholders are in place).
- **Tier-3 market-wide features are out of reach by design** (rank
  percentiles, IHSG median P/E, relative strength) — they need all-universe
  data that lazy backfill deliberately never accumulates.
- **KSEI / SID investor-count and foreign-flow data**: researched, no free
  API; would need a paid provider. The feasible free alternative is the IDX
  `GetCompanyProfilesDetail` → `PemegangSaham` shareholder breakdown
  (controlling / >5% / public float / treasury), **not yet implemented** —
  the user was asked whether to show the full named list or a category
  rollup and never answered.
- Edit-transaction modal deliberately does NOT auto-reprice on date change
  (it holds recorded data, unlike the add modal).
- **Small unflagged corporate actions still slip through.** Yahoo records
  stock *splits* (RAJA has two, and yfinance applies them) but had no event
  at all for PACK's action, leaving a raw 3280 → 272 cliff. Our detector
  catches ratios outside a deliberately wide 0.55–1.8 band — safe because IDX
  auto-rejection caps a session at ~20–35% — so a ~1.5:1 action would be
  missed. Widening the band risks mistaking small-cap volatility for an
  action and corrupting good prices. To re-audit after adding tickers:

  ```sql
  WITH g AS (SELECT s.ticker, ph.trade_date, ph.close,
    LAG(ph.close) OVER (PARTITION BY ph.security_id ORDER BY ph.trade_date) AS prev
    FROM price_history ph JOIN securities s ON s.id = ph.security_id
    WHERE s.kind = 'stock')
  SELECT ticker, trade_date, prev, close, round(close::numeric/prev, 4) AS ratio
  FROM g WHERE prev > 0 AND (close::numeric/prev >= 1.8
                          OR close::numeric/prev <= 0.55);
  ```
  Fix any hit with `python -m app.sync backfill --ticker XXXX`. Last audit:
  clean across all 37 tracked tickers / 42.690 bars.
- IDX holidays are not modelled anywhere (harmless: syncs no-op).
- Cross-file test dependencies exist (e.g. `test_stocks.py` alone fails
  because `AAAA` is seeded by `test_performance.py`). Run the whole suite.
- P/FCF from Yahoo's `info` uses their levered-FCF definition and can diverge
  wildly from OCF−capex; the statements-derived `fcf_ttm` is the honest one.
- No dividend tracking, no tax-lot accounting, no multi-currency (v2 roadmap).

## Running it

```sh
docker compose up -d                                   # postgres + API :8000
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed_demo    # demo@arus.id / arus-demo-123
cd frontend && npm install && npm run dev              # :5173
```

## Gotchas learned the hard way

- **Windows + PowerShell**: git commit messages must avoid `"` (breaks
  native-arg quoting) — use single-quoted here-strings.
- **uvicorn `--reload` file watcher crashes** on the Windows bind mount
  (`WatchfilesRustInternalError`) and used to kill the container silently;
  the restart policy now covers it.
- **Docker Desktop frequently needs restarting** between sessions; the engine
  reports "unable to start" until it is relaunched.
- **Modals must render through the portal** in `ui.tsx` — an ancestor
  `transform` (the `.rise` entry animation) traps `position: fixed`.
- IDX endpoints sit behind Cloudflare and intermittently 403; the fetcher's
  retry/backoff gets through.
- **Only ~37 of 963 tickers have price history, and that is correct** — lazy
  backfill (decision 6). Do not "fix" it by backfilling the universe.
- **TradingView Lightweight Charts is a renderer, not a data feed.** If a
  chart looks wrong, the bars in Postgres are wrong; the library only draws
  what it is given. (The embed widget would use TradingView's own data and
  bypass the whole pipeline — that is why it was not used.)
