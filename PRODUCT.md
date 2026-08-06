# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: the builder as a real IDX investor.** Someone tracking mock
portfolios of Indonesian (IDX) stocks — funding a portfolio with cash,
recording buy/sell orders in board lots, and checking value, performance
against the IHSG, and per-stock detail on a repeat daily-to-weekly cadence.
The design serves this working use first: scanability, density, and speed of
the recurring task.

**Secondary: recruiters and portfolio reviewers.** Arus is also a CS-student
portfolio project, and reviewers will open it cold. Their legibility is
handled by the one-command demo seed, the README, and screenshots — *not* by
diluting the working UI. Where the two conflict, daily use wins.

## Product Purpose

Record IDX stock transactions as the single source of truth and derive
everything else from them: holdings, cash balance, daily valuation series,
time-weighted performance versus the IHSG, risk analytics, allocation, and
per-stock detail with five years of history, fundamentals, and financial
statements.

Success means the project is public on GitHub with CI green, screenshots in
the README, and a hosted live demo anyone can click. As of this record it has
never been pushed to a remote — that is the largest open gap.

## Positioning

A brokerage-honest mock tracker built to IDX's actual mechanics rather than a
generic stock dashboard localized after the fact:

- Board lots at the edge, shares in the core (1 lot = 100 shares), enforced by
  a database check constraint.
- Whole-rupiah `BIGINT` money end to end — no floats anywhere in the money
  path, because IDX prices have no decimals.
- Cash funds every buy. A new portfolio must record a deposit before it can
  trade, exactly like funding a brokerage account.
- IDX tick-size steppers, percentage broker fees, and back-dated trades priced
  at that day's close.

Not a trading platform and not a data product: nothing executes real trades,
and it is personal / non-commercial by licensing necessity (IDX terms restrict
commercial redistribution; Yahoo Finance data has its own usage limits).

## Operating Context

- The IDX trading day on an Asia/Jakarta clock: quotes refresh Mon–Fri
  09:00–16:00, daily bars land 18:30, the universe syncs 21:00, fundamentals
  and statements on Saturday mornings. Data is delayed, never real-time.
- Local development on Windows: Docker Compose runs Postgres + the API, the
  Vite dev server runs separately on the host. Background jobs only run while
  containers are up, so a startup catch-up replays what was missed.
- Users compare against the IHSG benchmark and think in Indonesian
  conventions: `id-ID` number formatting, thousands separated by dots, rupiah.
- Evaluation scene: a reviewer clones or opens the demo, signs in as the seeded
  demo user, and forms an opinion in a few minutes.

## Capabilities and Constraints

**Capabilities.** Auth (bcrypt + JWT); portfolio CRUD; a cash ledger of
deposits and withdrawals with a derived balance; broker-style order entry
(lots slider bounded by cash or holdings, tick-size steppers, percentage fees,
price prefill); edit and delete transactions with ledger-integrity guards;
holdings, allocation with concentration flags, realized P&L (average cost,
including closed positions); performance series and metrics by range; global
ticker search; per-stock pages with candles, five years of history, cached
statistics, ~30 curated fundamentals, and Tier-2 financial statements with
derived solvency/efficiency metrics, Altman Z'' and Piotroski F.

**Load-bearing constraints.** Transactions are the source of truth — holdings
and cash balance are derived, never stored. Request handlers never call an
external API; everything is served from Postgres and only `app/sync/*` touches
IDX or Yahoo. Price history is backfilled lazily per ticker on first touch,
never across the whole ~963-ticker universe.

**Consequences that future work must respect.** Market-wide features (rank
percentiles, IHSG median P/E, relative strength) are not feasible without
reversing the lazy-backfill design. Only a few dozen tickers have price
history, and that is correct. Metrics use time-weighted returns so deposits
never masquerade as gains; the chart shows raw market value.

**Terminology.** Lot (100 shares), IHSG (the IDX composite benchmark),
TWR (time-weighted return), tick size, board, delisting, backfill.

**Explicitly undecided / out of scope.** The IDX shareholder breakdown
(`GetCompanyProfilesDetail` → `PemegangSaham`: controlling / >5% / public
float / treasury) is deferred — do not invent a presentation for it. KSEI/SID
investor-count and foreign-flow data have no free source. Dividend tracking,
tax-lot accounting, realized-P&L tax treatment, and US stocks with
multi-currency are v2 roadmap, not current scope.

## Brand Commitments

- **Name: Arus.** Demo identity `demo@arus.id`.
- **Light-only visual system, "Arus / Broadsheet"** (cool porcelain +
  ink-indigo). Binding. Dark fintech was proposed and rejected twice.
- **It must never read as a generic AI dashboard.** This is a stated
  requirement, not a preference.
- Voice in existing docs and UI: plain, factual, unhyped; methodology stated
  rather than implied.

## Evidence on Hand

- Working product with a real data pipeline against live IDX and Yahoo
  sources; 79 passing backend tests; CI configured for pytest plus frontend
  type-check and build.
- One-command demo seed (`python -m app.seed_demo`) producing a demo user with
  roughly two years of portfolio history and real backfilled prices.
- Documented data-quality work: 905 of 963 truncated company names corrected
  from the IDX profiles endpoint, and back-adjustment of corporate actions
  Yahoo never recorded.
- `README.md` and `HANDOFF.md` are accurate, current project records.

**Absences future work must not fabricate.** No screenshots exist yet
(README has placeholders). CI has never actually run — no remote is
configured. There are no users, no testimonials, no customers, no benchmarks
against other products, no pricing, no deployment, and no uptime record.

## Product Principles

1. **Derive, never store.** Holdings, cash balance, and P&L are computed from
   the transaction ledger. Any feature that would introduce a second, stored
   copy of a derivable fact is wrong by construction.
2. **IDX mechanics are the spec.** Lots, tick sizes, whole rupiah, broker fee
   percentages, the Jakarta trading clock. Generic stock-app conventions do
   not override how the exchange actually works.
3. **Read paths are local.** Anything the interface needs comes from Postgres.
   Freshness is a background-job problem, never a request-time one — which
   means the UI must be honest about delayed data rather than implying live.
4. **State the methodology.** TWR versus raw market value, average-cost
   realized P&L, the risk-free rate assumption, delayed quotes. Where a number
   involves a choice, the choice is visible rather than implied.
5. **Daily use sets the bar; the demo carries the reviewer.** Depth is proven
   by the seeded demo, README, and screenshots — not by making the working
   interface louder or more explanatory than a repeat user needs.
