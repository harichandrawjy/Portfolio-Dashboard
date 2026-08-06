import { ArrowLeft, CloudArrowDown } from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  api,
  type Fundamentals,
  type RangeKey,
  type SecurityStats,
} from "../api/client";
import { FinancialsPanel } from "../components/FinancialsPanel";
import { StockChart } from "../components/StockChart";
import {
  Button,
  EmptyState,
  ErrorNote,
  Panel,
  PanelHeader,
  Skeleton,
  WhatIsThis,
} from "../components/ui";
import { useAsync } from "../lib/hooks";
import {
  DASH,
  fmtAsOf,
  fmtDate,
  fmtDec,
  fmtNumCompact,
  fmtPct,
  fmtRp,
  fmtRpCompact,
  fmtSignedRp,
  signClass,
} from "../lib/format";

export function StockPage() {
  const { ticker = "" } = useParams();
  const symbol = ticker.toUpperCase();
  const [range, setRange] = useState<RangeKey>("1y");
  // Off by default: the page is about this stock, and overlaying the index
  // on first paint makes a single-stock chart read as a comparison nobody
  // asked for. It stays one click away.
  const [showIhsg, setShowIhsg] = useState(false);
  const [backfillTimedOut, setBackfillTimedOut] = useState(false);

  // A timeout belongs to the ticker that timed out. Without this reset the
  // next never-priced ticker renders "no price data" while it is in fact
  // still backfilling.
  useEffect(() => {
    setBackfillTimedOut(false);
  }, [symbol]);

  const detail = useAsync(() => api.securityDetail(symbol), [symbol]);
  const prices = useAsync(
    () => api.securityPrices(symbol, range),
    [symbol, range, detail.data?.has_history],
  );
  const position = useAsync(() => api.securityPosition(symbol), [symbol]);
  const financials = useAsync(
    () => api.securityFinancials(symbol),
    [symbol, detail.data?.has_history],
  );

  // First visit to a never-priced ticker: kick the lazy backfill and poll
  // until history (and the stat cache computed at its tail end) appears.
  const polling = useRef(false);
  useEffect(() => {
    if (!detail.data || detail.data.has_history || polling.current) return;
    polling.current = true;
    let cancelled = false;
    (async () => {
      const res = await api.ensurePrices(symbol).catch(() => null);
      if (res === null || res.status === "unavailable") {
        if (!cancelled) setBackfillTimedOut(true);
        return;
      }
      for (let i = 0; i < 12; i++) {
        await new Promise((r) => setTimeout(r, 2500));
        if (cancelled) return;
        const d = await api.securityDetail(symbol).catch(() => null);
        if (d?.has_history && d.stats) {
          if (!cancelled) detail.reload();
          return;
        }
      }
      if (!cancelled) setBackfillTimedOut(true);
    })();
    return () => {
      cancelled = true;
      polling.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.data?.has_history, symbol]);

  // Stable identities: inline `?? []` mints a new array every render, and both
  // are chart-effect deps — the chart was being torn down and rebuilt on each
  // render whenever the ticker was not held.
  const points = useMemo(() => prices.data?.points ?? [], [prices.data]);
  const markers = useMemo(
    () => position.data?.transactions ?? [],
    [position.data],
  );

  // Break-even for this ticker, drawn on the chart so the price has something
  // personal to be measured against. The same ticker can be held in several
  // portfolios at different costs, so this is the SHARE-WEIGHTED average
  // across all of them — averaging the per-portfolio averages would let a
  // one-lot position count as much as a hundred-lot one. Derived from
  // cost_basis rather than avg_cost_per_share so fees are included, matching
  // the "Avg cost" column in the holdings table.
  const avgCost = useMemo(() => {
    const rows = position.data?.positions ?? [];
    const shares = rows.reduce((n, r) => n + r.shares, 0);
    if (shares <= 0) return null;
    const cost = rows.reduce((n, r) => n + r.cost_basis, 0);
    return Math.round(cost / shares);
  }, [position.data]);

  const d = detail.data;
  const displayPrice = d?.quote_price ?? d?.last_close ?? null;
  const isFetchingHistory = d != null && !d.has_history && !backfillTimedOut;

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-4 py-8">
      <Link
        to="/" className="w-wide -my-1 flex w-max items-center gap-1.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3 outline-none transition-colors hover:text-accent focus-visible:ring-2 focus-visible:ring-accent"
      >
        <ArrowLeft size={12} weight="bold" /> Portfolios
      </Link>

      {detail.error ? (
        <Panel>
          {/* only a 404 means the ticker is unknown — telling someone to
              check their spelling after a 500 sends them the wrong way */}
          {detail.status === 404 ? (
            <EmptyState
              title="Unknown ticker" body={`${symbol} is not in the IDX universe. Check the spelling, or run a universe sync if it listed recently.`}
            />
          ) : (
            <EmptyState
              title={`Couldn't load ${symbol}`}
              body={detail.error}
              action={
                <Button variant="ghost" onClick={detail.reload}>
                  Try again
                </Button>
              }
            />
          )}
        </Panel>
      ) : detail.loading || !d ? (
        <HeaderSkeleton />
      ) : (
        <>
          {/* ------------------------------------------------ header */}
          <div
            className="rise flex flex-wrap items-end justify-between gap-4 border-b-2 border-ink pb-6" style={{ "--rise": 0 } as React.CSSProperties}
          >
            <div>
              <div className="flex items-center gap-3">
                {/* the ticker is the page's nameplate — condensed, heaviest */}
                <h1 className="w-condensed text-[clamp(2rem,4.5vw,2.75rem)] font-extrabold uppercase leading-none tracking-[-0.02em] text-ink">
                  {d.ticker}
                </h1>
                {!d.is_active && (
                  <span className="bg-neg px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.1em] text-white">
                    Delisted
                  </span>
                )}
              </div>
              <p className="mt-2 text-[13px] text-ink-2">{d.name}</p>
              <p className="w-wide mt-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                {[d.sector, d.board ? `${d.board} board` : null]
                  .filter(Boolean)
                  .join(" · ") || DASH}
              </p>
            </div>
            {/* Right-aligned only once it sits opposite the name block. On a
                phone it wraps onto its own line and must read from the same
                left edge as the heading above it. */}
            <div className="sm:text-right">
              <p className="tnum w-condensed text-[clamp(2.5rem,5.5vw,3.5rem)] font-extrabold leading-[0.88] tracking-[-0.03em] text-ink">
                {fmtRp(displayPrice)}
              </p>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-[13px] sm:justify-end">
                {/* no quote means no change to show — a bare em-dash in front
                    of "close, 30 Jul" just reads as stray punctuation */}
                {d.quote_change_pct != null && (
                  <span className={`tnum ${signClass(d.quote_change_pct)}`}>
                    {fmtPct(d.quote_change_pct, true)}
                  </span>
                )}
                <span className="text-ink-3">
                  {d.quote_as_of
                    ? `as of ${fmtAsOf(d.quote_as_of)}`
                    : d.last_close_date
                      ? `${d.quote_change_pct != null ? "close" : "Close"}, ${fmtDate(d.last_close_date)}`
                      : "No price yet"}
                </span>
              </p>
            </div>
          </div>

          {/* -------------------------------- first-visit backfill */}
          {isFetchingHistory ? (
            <Panel>
              <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                <CloudArrowDown size={28} weight="light" className="text-accent" />
                <p className="text-[13px] font-medium text-ink">
                  Fetching five years of daily history for {d.ticker}
                </p>
                <p className="max-w-[42ch] text-[13px] leading-relaxed text-ink-3">
                  First visit to this ticker. Prices are loading in the
                  background; the chart and statistics appear here in a few
                  seconds.
                </p>
                <Skeleton className="mt-2 h-[160px] w-full max-w-xl" />
              </div>
            </Panel>
          ) : !d.has_history ? (
            <Panel>
              <EmptyState
                title="No price data available" body="Yahoo has no daily bars for this ticker yet. It may be newly listed or suspended; the nightly sync will keep trying."
              />
            </Panel>
          ) : (
            <>
              <div className="rise" style={{ "--rise": 1 } as React.CSSProperties}>
                <StockChart
                  points={points}
                  loading={prices.loading}
                  error={prices.error}
                  range={range}
                  onRangeChange={setRange}
                  showIhsg={showIhsg}
                  onToggleIhsg={() => setShowIhsg((v) => !v)}
                  markers={markers}
                  quotePrice={d.quote_price}
                  provisional={prices.data?.provisional ?? null}
                  avgCost={avgCost}
                />
              </div>

              {position.data?.held ? (
                <div
                  className="rise grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" style={{ "--rise": 2 } as React.CSSProperties}
                >
                  <StatsPanel stats={d.stats} onReload={detail.reload} />
                  <PositionPanel position={position.data} />
                </div>
              ) : (
                <div className="rise" style={{ "--rise": 2 } as React.CSSProperties}>
                  {position.error && (
                    <div className="mb-5">
                      <ErrorNote
                        message={`Couldn't check whether you hold ${d.ticker}: ${position.error}`}
                      />
                    </div>
                  )}
                  <StatsPanel stats={d.stats} onReload={detail.reload} />
                </div>
              )}

              <div className="rise" style={{ "--rise": 3 } as React.CSSProperties}>
                <FundamentalsPanel fundamentals={d.fundamentals} />
              </div>

              <div className="rise" style={{ "--rise": 4 } as React.CSSProperties}>
                <FinancialsPanel
                  financials={financials.data}
                  loading={financials.loading}
                  error={financials.error}
                />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

/** Mirrors the real header's boxes and border so the page does not jump
 *  when the data lands. */
function HeaderSkeleton() {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div>
        <Skeleton className="h-9 w-28" />
        <Skeleton className="mt-2 h-5 w-52" />
        <Skeleton className="mt-1.5 h-4 w-40" />
      </div>
      <div className="flex flex-col items-end">
        <Skeleton className="h-[42px] w-44" />
        <Skeleton className="mt-2 h-4 w-36" />
      </div>
    </div>
  );
}

const RETURN_TILES: { key: keyof SecurityStats; label: string }[] = [
  { key: "return_1d_pct", label: "1D" },
  { key: "return_1w_pct", label: "1W" },
  { key: "return_1mo_pct", label: "1M" },
  { key: "return_ytd_pct", label: "YTD" },
  { key: "return_1y_pct", label: "1Y" },
  { key: "return_5y_pct", label: "5Y" },
];

function StatsPanel({
  stats,
  onReload,
}: {
  stats: SecurityStats | null;
  onReload: () => void;
}) {
  return (
    <Panel tone="flat">
      <PanelHeader seq="02" title="Statistics" />
      {stats === null ? (
        /* the copy used to say "reload in a moment" with nothing to press */
        <EmptyState
          title="Statistics are being computed" body="Stats build right after the first price backfill and refresh nightly." action={
            <Button variant="ghost" onClick={onReload}>
              Check again
            </Button>
          }
        />
      ) : (
        <div className="px-5 pb-5">
          {/* one strip with internal dividers, not six identical boxes */}
          {/* divide-y too: at three columns the tiles wrap to two rows and
              vertical rules alone leave the rows touching */}
          <div className="grid grid-cols-3 divide-x divide-y divide-line/60 overflow-hidden bg-ink/[0.03] ring-1 ring-line sm:grid-cols-6 sm:divide-y-0">
            {RETURN_TILES.map(({ key, label }) => {
              const v = stats[key] as number | null;
              return (
                <div key={key} className="px-2 py-3 text-center">
                  <p className="text-[11px] text-ink-3">{label}</p>
                  <p
                    className={`tnum mt-1 text-[13px] font-medium ${signClass(v)}`}
                  >
                    {fmtPct(v, true)}
                  </p>
                </div>
              );
            })}
          </div>

          <dl className="mt-4 grid grid-cols-1 gap-x-8 gap-y-2 text-[13px] sm:grid-cols-2">
            <StatRow
              label="52-week range" value={
                stats.low_52w != null && stats.high_52w != null
                  ? `${fmtRp(stats.low_52w)} – ${fmtRp(stats.high_52w)}`
                  : DASH
              }
            />
            <StatRow
              label="All-time range (5y data)" value={
                stats.low_all != null && stats.high_all != null
                  ? `${fmtRp(stats.low_all)} – ${fmtRp(stats.high_all)}`
                  : DASH
              }
            />
            <StatRow
              label="Avg daily volume (3mo)" value={
                stats.avg_volume_3mo != null
                  ? `${fmtNumCompact(stats.avg_volume_3mo)} shares`
                  : DASH
              }
            />
            <StatRow
              label="Volatility (1y, annualized)" value={fmtPct(stats.volatility_1y_pct)}
            />
            <StatRow
              label="Max drawdown (1y)" value={fmtPct(stats.max_drawdown_1y_pct)}
            />
            <StatRow label="Beta vs IHSG (1y)" value={fmtDec(stats.beta_1y)} />
          </dl>

          <div className="mt-4">
            <WhatIsThis label="risk statistics">
              <strong className="font-medium text-ink">Volatility</strong> is how
              much the daily price moves, annualised — higher means a bumpier
              ride.{" "}
              <strong className="font-medium text-ink">Max drawdown</strong> is
              the worst peak-to-trough fall in the last year.{" "}
              <strong className="font-medium text-ink">Beta</strong> compares the
              stock to the IHSG: 1,00 moves with the index, above 1,00 amplifies
              it, below 1,00 dampens it, and a negative beta moves against it.
            </WhatIsThis>
          </div>

          <p className="mt-3 text-xs text-ink-3">
            Computed nightly from stored history · updated {fmtAsOf(stats.computed_at)}
          </p>
        </div>
      )}
    </Panel>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line pb-1.5">
      <dt className="text-ink-3">{label}</dt>
      <dd className="tnum text-ink">{value}</dd>
    </div>
  );
}

function PositionPanel({
  position,
}: {
  position: {
    positions: {
      portfolio_id: string;
      portfolio_name: string;
      lots: number;
      avg_cost_per_share: number;
      market_value: number | null;
      unrealized_pnl: number | null;
      unrealized_pnl_pct: number | null;
      pct_of_portfolio: number | null;
    }[];
  };
}) {
  return (
    <Panel>
      <PanelHeader seq="03" title="Your position" />
      <div className="flex flex-col gap-4 px-5 pb-5">
        {position.positions.map((p) => (
          <div key={p.portfolio_id}>
            <Link
              to={`/portfolios/${p.portfolio_id}`}
              className="-my-1.5 inline-block py-1.5 text-[13px] font-medium text-ink outline-none transition-colors hover:text-accent focus-visible:ring-2 focus-visible:ring-accent"
            >
              {p.portfolio_name}
            </Link>
            <dl className="mt-2 flex flex-col gap-1.5 text-[13px]">
              <PosRow label="Lots held" value={String(p.lots)} />
              <PosRow
                label="Avg cost" value={fmtRp(Math.round(p.avg_cost_per_share))}
              />
              <PosRow label="Market value" value={fmtRp(p.market_value)} />
              <div className="flex items-baseline justify-between gap-4">
                <dt className="text-ink-3">Unrealized P&L</dt>
                <dd
                  className={`tnum text-right ${signClass(p.unrealized_pnl)}`}
                >
                  {fmtSignedRp(p.unrealized_pnl)}
                  <span className="ml-1.5 text-xs opacity-80">
                    {fmtPct(p.unrealized_pnl_pct, true)}
                  </span>
                </dd>
              </div>
              <PosRow
                label="Share of portfolio" value={fmtPct(p.pct_of_portfolio)}
              />
            </dl>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function PosRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-ink-3">{label}</dt>
      <dd className="tnum text-ink">{value}</dd>
    </div>
  );
}

/** Per-share figures like EPS can be legitimately sub-rupiah on IDX
 *  (GOTO's EPS is -0,61); rounding those to whole Rp would lie. */
function fmtRpFine(n: number | null): string {
  if (n == null) return DASH;
  if (Math.abs(n) < 100) {
    return (
      (n < 0 ? "-" : "") +
      "Rp " +
      Math.abs(n).toLocaleString("id-ID", { maximumFractionDigits: 2 })
    );
  }
  return fmtRp(Math.round(n));
}

function FundamentalsPanel({
  fundamentals: f,
}: {
  fundamentals: Fundamentals | null;
}) {
  if (f === null) {
    return (
      <Panel tone="flat">
        <PanelHeader seq="04" title="Fundamentals" />
        <div className="px-5 pb-5">
          <p className="text-[13px] leading-relaxed text-ink-3">
            Not fetched yet. Fundamentals load on a ticker's first visit and
            refresh weekly; Yahoo's coverage of IDX names is patchy, so some
            fields may stay empty.
          </p>
        </div>
      </Panel>
    );
  }

  const x = f.extra;
  const cur = x?.financial_currency ?? null;
  const ratio = (v: number | null | undefined) =>
    v != null ? fmtDec(v) + "×" : DASH;
  const money = (v: number | null | undefined) => {
    if (v == null) return DASH;
    return cur && cur !== "IDR"
      ? `${cur} ${fmtNumCompact(v)}`
      : fmtRpCompact(v);
  };
  const count = (v: number | null | undefined) =>
    v != null ? fmtNumCompact(v) : DASH;

  // Everything stays expanded. This is an instrument for a repeat user, and
  // PRODUCT.md puts daily use ahead of a cold reader: folding groups charges
  // that user a click per visit and breaks find-in-page across ~40 figures.
  const groups: { title: string; rows: [string, string][] }[] = [
    {
      title: "Valuation",
      rows: [
        ["Market cap", f.market_cap != null ? fmtRpCompact(f.market_cap) : DASH],
        [
          "Enterprise value",
          x?.enterprise_value != null ? fmtRpCompact(x.enterprise_value) : DASH,
        ],
        ["Trailing P/E", ratio(f.pe_ratio)],
        ["Forward P/E", ratio(x?.forward_pe)],
        ["Earnings yield", fmtPct(x?.earnings_yield_pct)],
        ["PEG ratio", fmtDec(x?.peg_ratio)],
        ["Price / sales", ratio(x?.price_to_sales)],
        ["Price / book", ratio(x?.price_to_book)],
        ["Price / cash flow", ratio(x?.price_to_cashflow)],
        ["Price / free cash flow", ratio(x?.price_to_fcf)],
        ["EV / revenue", ratio(x?.ev_to_revenue)],
        ["EV / EBITDA", ratio(x?.ev_to_ebitda)],
      ],
    },
    {
      title: "Profitability",
      rows: [
        ["Gross margin", fmtPct(x?.gross_margin_pct)],
        ["Operating margin", fmtPct(x?.operating_margin_pct)],
        ["EBITDA margin", fmtPct(x?.ebitda_margin_pct)],
        ["Profit margin", fmtPct(x?.profit_margin_pct)],
        ["Return on assets", fmtPct(x?.roa_pct)],
        ["Return on equity", fmtPct(x?.roe_pct)],
      ],
    },
    {
      title: cur && cur !== "IDR" ? `Per share (${cur})` : "Per share",
      rows: [
        ["EPS (trailing)", fmtRpFine(f.eps)],
        ["Revenue / share", fmtRpFine(x?.revenue_per_share ?? null)],
        ["Cash / share", fmtRpFine(x?.cash_per_share ?? null)],
        ["Free cash flow / share", fmtRpFine(x?.fcf_per_share ?? null)],
        ["Book value / share", fmtRpFine(f.book_value)],
      ],
    },
    {
      title: cur && cur !== "IDR" ? `Income (${cur})` : "Income",
      rows: [
        ["Revenue (ttm)", money(x?.revenue)],
        ["Revenue growth (yoy)", fmtPct(x?.revenue_growth_pct, true)],
        ["EBITDA", money(x?.ebitda)],
        ["Net income", money(x?.net_income)],
        ["EPS (trailing)", fmtRpFine(f.eps)],
        ["Earnings growth (yoy)", fmtPct(x?.earnings_growth_pct, true)],
      ],
    },
    {
      title:
        cur && cur !== "IDR" ? `Balance & cash (${cur})` : "Balance & cash",
      rows: [
        ["Total cash", money(x?.total_cash)],
        ["Total debt", money(x?.total_debt)],
        ["Net debt", money(x?.net_debt)],
        ["Debt / equity", fmtPct(x?.debt_to_equity_pct)],
        ["Current ratio", fmtDec(x?.current_ratio)],
        ["Quick ratio", fmtDec(x?.quick_ratio)],
        ["Operating cash flow", money(x?.operating_cash_flow)],
        ["Free cash flow", money(x?.free_cash_flow)],
      ],
    },
    {
      title: "Shares",
      rows: [
        ["Outstanding", count(x?.shares_outstanding)],
        ["Float", count(x?.float_shares)],
        ["Held by insiders", fmtPct(x?.held_insiders_pct)],
        ["Held by institutions", fmtPct(x?.held_institutions_pct)],
        ["Avg volume (10d)", count(x?.avg_volume_10d)],
      ],
    },
    {
      title: "Dividends",
      rows: [
        ["Forward yield", fmtPct(f.dividend_yield_pct)],
        ["Forward rate / share", fmtRpFine(x?.forward_dividend_rate ?? null)],
        ["Trailing yield", fmtPct(x?.trailing_dividend_yield_pct)],
        ["5y average yield", fmtPct(x?.five_year_avg_dividend_yield_pct)],
        ["Payout ratio", fmtPct(x?.payout_ratio_pct)],
        [
          "Ex-dividend date",
          x?.ex_dividend_date ? fmtDate(x.ex_dividend_date) : DASH,
        ],
      ],
    },
  ];

  return (
    <Panel tone="flat">
      <PanelHeader seq="04" title="Fundamentals" />
      <div className="px-5 pb-5">
        {/* newspaper-style column spread instead of one long skinny list */}
        <div className="grid grid-cols-1 gap-x-10 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((g) => (
            <div key={g.title} className="border-t border-line pt-3">
              <p className="mb-2 text-xs font-medium text-ink-3">{g.title}</p>
              <dl className="flex flex-col gap-1.5 text-[13px]">
                {g.rows.map(([label, value]) => (
                  <PosRow key={label} label={label} value={value} />
                ))}
              </dl>
            </div>
          ))}
        </div>
        <p className="mt-5 text-xs text-ink-3">
          From Yahoo, refreshed weekly · updated {fmtDate(f.last_updated)}
        </p>
      </div>
    </Panel>
  );
}
