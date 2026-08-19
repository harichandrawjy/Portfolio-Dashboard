# Arus — project handoff

Context for picking this project up in a fresh session. Read this plus
`README.md` and `DEPLOY.md`; the frontend design contract lives in Claude
memory (`frontend-design-direction`) and in `.claude/skills`.

**Live at https://arus-idx.duckdns.org.** See *Deployment* below.

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
docker-compose.prod.yml     prod overlay — uses !override / !reset, load-bearing
Caddyfile                   TLS + static + /api reverse proxy, one origin
DEPLOY.md                   full deployment procedure
scripts/bootstrap-host.sh   fresh-VM prep: docker, iptables, swap, Compose check
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
    optimize.py             PURE mean-variance: simplex projection, projected
                            gradient, CAPM/log mu, frontier + the three selectors
    demo.py                 per-visitor demo accounts (mint, 24h TTL, purge)
    ratelimit.py            sliding-window limiter; rightmost X-Forwarded-For hop
    performance.py          daily valuation series (replays transactions), TWR
    pnl.py                  PURE realized P&L (average-cost)
    scheduler.py            APScheduler jobs + enqueue_backfill()
    seed_demo.py            one-command demo seed
    routers/                auth, portfolios, performance, securities, health
    sync/                   ALL external data: idx, prices, stats, fundamentals,
                            statements, universe, catchup, __main__ (CLI)
    data/idx_universe.csv   963-ticker snapshot — now the PRIMARY source, not
                            a fallback; the live IDX crawl is opt-in only
  alembic/versions/         0001..0008
  tests/                    18 test files, 159 tests
frontend/
  Dockerfile                multi-stage build; Caddy serves the static output
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

   **A BUY may not be dated before the first cash flow** (`_reject_buy_before_
   funding`, enforced on both create and edit). That exclusion above is what
   made the rule enforceable-looking but not enforced: the affordability
   guards compute the balance with the *same* exclusion, so a buy dated behind
   the funding was left out of the very sum meant to catch it and cost
   nothing. Two ways in, both now closed — deposit 94jt then buy 84jt dated
   earlier (accepted, balance still reported 94jt), or record an affordable
   buy and edit its date backwards (the `balance < 0` guard stops seeing the
   cost). SELL is deliberately unrestricted: it releases cash, and blocking it
   would strand imported history. Reads still tolerate pre-ledger trades and
   report them via `uncounted_trades`, so existing portfolios do not lurch
   negative — the rule is enforced on write only.
10. **Frontend design must not read as a generic AI dashboard.** Light-only.
    The current system is **"Raster"** — Swiss modernist: one grotesk
    (Archivo Variable, weight + width axes), black rules and numbered
    sections instead of cards, zero radius, zero shadow, and a single deep-sea blue
    used only as a full flat field. `DESIGN.md` is the contract; the
    `impeccable` hook validates literal font sizes against its type ramp.
    The user rejected dark fintech twice — do not propose it. See the memory
    file before touching styling.

## Deployment

One box runs Caddy + backend + Postgres. Four decisions hold it together:

1. **One origin, no CORS.** The frontend hardcodes `BASE = "/api"`; Caddy
   serves the static build and proxies `/api` from the same host, so that path
   works unchanged. Splitting the frontend onto its own host would need CORS
   middleware (the app has none) and an env-driven absolute API URL.
2. **The backend must stay awake.** APScheduler runs in-process, so a host that
   sleeps stops the quote and bar schedule outright. There is no separate
   worker. Single uvicorn worker, too — two workers means two schedulers racing.
3. **Compose merge semantics.** List fields *append*, so `ports: []` does
   nothing. `docker-compose.prod.yml` uses `!override` / `!reset` and they are
   load-bearing; they need Compose ≥ 2.24 or they are ignored **silently**.
   `bootstrap-host.sh` asserts the version for this reason.
4. **`SECRET_KEY` must be real.** The app refuses to boot in production on the
   dev placeholder or anything under 32 chars; `APP_ENV=production` turns the
   check on. Generate with `openssl rand -hex 32`.

## Scheduled jobs (Asia/Jakarta)

| Job | When |
|---|---|
| Daily bars | Mon–Fri 18:30 (then rebuilds the stat cache) |
| Quote refresh | Mon–Fri 09:00–16:00, every 15 min |
| Fundamentals | Sat 06:00 |
| Statements | Sat 06:30 |
| Demo-account purge | daily 04:00 — drops per-visitor demo users past their 24h TTL |
| Startup catch-up | every boot — appends missed bars, refreshes quotes >30 min old |

**There is deliberately no scheduled universe sync.** It was removed: IDX's
terms bar the scraping method, and the crawl had never actually succeeded in
production anyway (Cloudflare 403). The bundled snapshot is the source now.

Jobs only run while containers are up, hence `restart: unless-stopped` plus
the catch-up. Manual override: `docker compose exec backend python -m app.sync
<universe|backfill|daily|quotes|stats|fundamentals|statements>`.

## Done (58 commits, all 11 original build steps + extras)

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
- Three UI redesigns → current light **"Raster"** (Swiss modernist) system.
  The rewrite replaced the three-font Playfair/Geist/JetBrains voice with a
  single variable grotesk; `tnum` support was verified in-browser first,
  because tabular figures are load-bearing for the money columns
- Automatic refresh: restart policy + startup catch-up
- **Data-quality fixes**: full company names (IDX's stock-list endpoint
  truncates at 30 chars; the profiles endpoint has the real one — 905 of 963
  names corrected), and back-adjustment of corporate actions Yahoo never
  recorded (`adjust_corporate_actions` in `sync/prices.py`)

**Shipped since, and deployed:**
- **Public deployment** on Oracle Always Free — Caddy + backend + Postgres on
  one box, Let's Encrypt TLS, `scripts/bootstrap-host.sh` for a fresh VM
- **Per-visitor demo accounts** (`POST /auth/demo`, 24h TTL, purged daily 04:00)
  replacing the single shared mutable demo login, plus a sliding-window limiter
- **Efficient frontier panel** — long-only mean-variance optimisation:
  - `optimize.py` is pure and dependency-light. Projected gradient descent with
    an exact simplex projection (Duchi et al. 2008) and a 1/λ_max step, chosen
    over SciPy to keep ~30 MB out of the image
  - Expected returns from **CAPM** (default) or **annualised log returns**,
    switchable in the panel. Σ stays on *simple* returns under both, because
    `wᵀΣw` is exact only for asset-additive returns
  - Three formulations read off one curve: min risk (τ→0), max Sharpe (golden
    section on τ), target return (bisection on τ)
  - Estimated over the **last complete calendar year** — 2025 now, 2026 from
    1 Jan 2027 (`frontier_window()`), rather than a rolling lookback, so the
    figures are quotable and do not drift nightly
- **IDX compliance**: scheduled crawl removed, snapshot committed, source
  credited in the UI with an access date
- **Name reconcile** (`--reconcile-names`) for drift the truncation guard
  cannot repair — a name that came back *longer* (a `PT ` prefix, ALL CAPS)
- Invested value surfaced per portfolio and per holding; broker-style
  two-line holdings header with allocation

**Test suite: 159 passing.** `docker compose exec backend pytest`

## Not done / known gaps

- **The frontier panel shows no uncertainty.** This is the biggest open item.
  Max Sharpe can render a confident `+50,66% · Sharpe 1,543` off 236 sessions,
  where the two-sigma band on that return is roughly ±60 percentage points.
  Two fixes were designed and not built: (a) flag the degenerate case where
  fewer than two holdings clear Rf, which currently renders as a 100%
  single-name allocation; (b) draw a ±2·SE band on the holding scatter points.
- **No automated backups.** Four manual `pg_dump` snapshots exist; nothing is
  scheduled.
- **Live URL is not in the README or the GitHub About.**
- **Python dependencies are unpinned.**
- `analytics.py` comments "~247 sessions/year"; measured 2022–25 is ~238. The
  252 constant elsewhere is a shared convention, not a measurement.
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
- **IDX holidays are handled by the index, not a calendar.** They were once
  listed here as "not modelled anywhere (harmless: syncs no-op)". Not
  harmless: Yahoo omits holidays from `^JKSE` but *synthesises* them for
  individual tickers, copying the previous close into O/H/L/C with volume 0.
  191 such rows reached `price_history` across eight 2026 holidays and drew
  bodiless candles on days the exchange was shut. Only the nightly path was
  affected — a five-year backfill request omits holidays on its own, which is
  why 2025's eleven-day Idul Fitri closure is simply absent from the data.

  `sync_daily` now fetches the benchmark window first and passes its dates to
  `_df_to_rows` as `sessions`: **if `^JKSE` printed nothing, nothing traded.**
  The naive filter — drop zero-volume flat bars — is wrong, because an
  illiquid stock with no trades on a real session produces an identical bar;
  892 days of stored history look like that and none may be dropped. A failed
  index fetch yields `sessions=None` and stores unfiltered, so a bad Yahoo
  night costs one holiday bar rather than a whole night of prices.

  Cleaning the 191 rows moved `volatility_1y_pct` up on 46 of 47 tickers
  (median +0,84%, max +1,46%) and `avg_volume_3mo` up a median +3,33%; the
  zeros had been padding both. `beta_1y` moved on none of them, because it
  aligns against IHSG and those dates never had an index bar to align to.
  The frontier was never affected — its window is calendar 2025.

  To re-audit:

  ```sql
  WITH ihsg AS (SELECT ph.trade_date FROM price_history ph
                JOIN securities s ON s.id = ph.security_id WHERE s.ticker = 'IHSG'),
       rng AS (SELECT min(trade_date) lo, max(trade_date) hi FROM ihsg)
  SELECT ph.trade_date, count(*) FROM price_history ph, rng
  WHERE ph.trade_date BETWEEN rng.lo AND rng.hi
    AND ph.trade_date NOT IN (SELECT trade_date FROM ihsg)
  GROUP BY ph.trade_date ORDER BY ph.trade_date;
  ```
- Cross-file test dependencies exist (e.g. `test_stocks.py` alone fails
  because `AAAA` is seeded by `test_performance.py`). Run the whole suite.
- P/FCF from Yahoo's `info` uses their levered-FCF definition and can diverge
  wildly from OCF−capex; the statements-derived `fcf_ttm` is the honest one.
- No dividend tracking, no tax-lot accounting, no multi-currency (v2 roadmap).

## Running it

Development:

```sh
docker compose up -d                                   # postgres + API :8000
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed_demo    # seeds the demo template
cd frontend && npm install && npm run dev              # :5173
```

Production — Oracle Always Free, x86 E2.1.Micro, 1 GB RAM + 2 GB swap
(A1 ARM had no capacity). `ssh ubuntu@161.118.254.84`, app in `~/arus`:

```sh
git pull
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

That one command builds the frontend too, and takes several minutes on this
box — run it in the background. Alembic migrates automatically on boot.

## Gotchas learned the hard way

- **Windows + PowerShell 5.1**: no `&&`, no ternary, no `??` — chaining with
  `&&` is a parser error. Commit messages must avoid `"`; prefer repeated `-m`
  flags over here-strings, whose closing `'@` must sit at column 0.
- **`docker compose cp x backend:/app/...` writes into the repo**, because
  `./backend` is bind-mounted. Scratch scripts land in `git status`. Copy to
  `/tmp` inside the container instead, and pass `-e PYTHONPATH=/app`.
- **Deploy watchers need the right completion condition.** Three separate ones
  reported a finished deploy as stalled: `pgrep -f "docker compose"` matched
  its own command line; a check for `"Up N hour"` failed when uptime was in
  days; and one waited on `arus-caddy-1 Started` during a backend-only change.
- **`bash -n` will not catch a bad heredoc substitution.** `${VAR:-a b's c}`
  fails at *runtime*, not parse time — an apostrophe opens a quote that never
  closes. Precompute the string into a variable instead.
- **The IDX Cloudflare block is not total.** Logs showing only 403s do not
  prove the crawl never lands; one success rewrote all 963 company names with
  `PT ` prefixes and shouty casing. Hence the snapshot-first design.
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
