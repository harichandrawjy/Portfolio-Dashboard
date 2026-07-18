import { ArrowLeft, CloudArrowDown } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, type RangeKey, type SecurityStats } from "../api/client";
import { StockChart } from "../components/StockChart";
import { EmptyState, Panel, PanelHeader, Skeleton } from "../components/ui";
import { useAsync } from "../lib/hooks";
import {
  DASH,
  fmtAsOf,
  fmtDate,
  fmtNumCompact,
  fmtPct,
  fmtRp,
  fmtSignedRp,
  signClass,
} from "../lib/format";

export function StockPage() {
  const { ticker = "" } = useParams();
  const symbol = ticker.toUpperCase();
  const [range, setRange] = useState<RangeKey>("1y");
  const [showIhsg, setShowIhsg] = useState(true);
  const [backfillTimedOut, setBackfillTimedOut] = useState(false);

  const detail = useAsync(() => api.securityDetail(symbol), [symbol]);
  const prices = useAsync(
    () => api.securityPrices(symbol, range),
    [symbol, range, detail.data?.has_history],
  );
  const position = useAsync(() => api.securityPosition(symbol), [symbol]);

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

  const d = detail.data;
  const displayPrice = d?.quote_price ?? d?.last_close ?? null;
  const isFetchingHistory = d != null && !d.has_history && !backfillTimedOut;

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-8">
      <Link
        to="/"
        className="flex w-max items-center gap-1.5 text-[13px] text-ink-3 transition-colors hover:text-ink-2"
      >
        <ArrowLeft size={14} weight="light" /> Portfolios
      </Link>

      {detail.error ? (
        <Panel>
          <EmptyState
            title="Unknown ticker"
            body={`${symbol} is not in the IDX universe. Check the spelling, or run a universe sync if it listed recently.`}
          />
        </Panel>
      ) : detail.loading || !d ? (
        <HeaderSkeleton />
      ) : (
        <>
          {/* ------------------------------------------------ header */}
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="font-mono text-2xl font-semibold text-ink">
                  {d.ticker}
                </h1>
                {!d.is_active && (
                  <span className="rounded-full bg-neg/10 px-2.5 py-0.5 text-[11px] font-medium text-neg ring-1 ring-neg/25">
                    Delisted
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-sm text-ink-2">{d.name}</p>
              <p className="mt-1 text-xs text-ink-3">
                {[d.sector, d.board ? `${d.board} board` : null]
                  .filter(Boolean)
                  .join(" · ") || DASH}
              </p>
            </div>
            <div className="text-right">
              <p className="tnum font-mono text-3xl font-semibold text-ink">
                {fmtRp(displayPrice)}
              </p>
              <p className="mt-0.5 flex items-center justify-end gap-2 text-[13px]">
                <span className={`tnum font-mono ${signClass(d.quote_change_pct)}`}>
                  {fmtPct(d.quote_change_pct, true)}
                </span>
                <span className="text-ink-3">
                  {d.quote_as_of
                    ? `as of ${fmtAsOf(d.quote_as_of)}`
                    : d.last_close_date
                      ? `close, ${fmtDate(d.last_close_date)}`
                      : "no price yet"}
                </span>
              </p>
            </div>
          </div>

          {/* -------------------------------- first-visit backfill */}
          {isFetchingHistory ? (
            <Panel>
              <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                <CloudArrowDown size={28} weight="light" className="text-accent" />
                <p className="text-sm font-medium text-ink">
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
                title="No price data available"
                body="Yahoo has no daily bars for this ticker yet. It may be newly listed or suspended; the nightly sync will keep trying."
              />
            </Panel>
          ) : (
            <>
              <StockChart
                points={prices.data?.points ?? []}
                loading={prices.loading}
                range={range}
                onRangeChange={setRange}
                showIhsg={showIhsg}
                onToggleIhsg={() => setShowIhsg((v) => !v)}
                markers={position.data?.transactions ?? []}
              />

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
                <StatsPanel stats={d.stats} />
                {position.data?.held && (
                  <PositionPanel position={position.data} />
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function HeaderSkeleton() {
  return (
    <div className="flex items-end justify-between">
      <div>
        <Skeleton className="h-8 w-28" />
        <Skeleton className="mt-2 h-4 w-48" />
      </div>
      <Skeleton className="h-9 w-36" />
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

function StatsPanel({ stats }: { stats: SecurityStats | null }) {
  return (
    <Panel>
      <PanelHeader title="Statistics" />
      {stats === null ? (
        <EmptyState
          title="Statistics are being computed"
          body="Stats build right after the first price backfill and refresh nightly. Reload in a moment."
        />
      ) : (
        <div className="px-5 pb-5">
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {RETURN_TILES.map(({ key, label }) => {
              const v = stats[key] as number | null;
              return (
                <div
                  key={key}
                  className="rounded-[8px] bg-panel-2 px-2 py-2 text-center ring-1 ring-line"
                >
                  <p className="text-[11px] text-ink-3">{label}</p>
                  <p className={`tnum mt-0.5 font-mono text-[13px] ${signClass(v)}`}>
                    {fmtPct(v, true)}
                  </p>
                </div>
              );
            })}
          </div>

          <dl className="mt-4 grid grid-cols-1 gap-x-8 gap-y-2 text-[13px] sm:grid-cols-2">
            <StatRow
              label="52-week range"
              value={
                stats.low_52w != null && stats.high_52w != null
                  ? `${fmtRp(stats.low_52w)} – ${fmtRp(stats.high_52w)}`
                  : DASH
              }
            />
            <StatRow
              label="All-time range (5y data)"
              value={
                stats.low_all != null && stats.high_all != null
                  ? `${fmtRp(stats.low_all)} – ${fmtRp(stats.high_all)}`
                  : DASH
              }
            />
            <StatRow
              label="Avg daily volume (3mo)"
              value={
                stats.avg_volume_3mo != null
                  ? `${fmtNumCompact(stats.avg_volume_3mo)} shares`
                  : DASH
              }
            />
            <StatRow
              label="Volatility (1y, annualized)"
              value={fmtPct(stats.volatility_1y_pct)}
            />
            <StatRow
              label="Max drawdown (1y)"
              value={fmtPct(stats.max_drawdown_1y_pct)}
            />
            <StatRow label="Beta vs IHSG (1y)" value={stats.beta_1y?.toFixed(2) ?? DASH} />
          </dl>

          <p className="mt-4 text-xs text-ink-3">
            Computed nightly from stored history · updated {fmtAsOf(stats.computed_at)}
          </p>
        </div>
      )}
    </Panel>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/50 pb-1.5">
      <dt className="text-ink-3">{label}</dt>
      <dd className="tnum font-mono text-ink">{value}</dd>
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
      <PanelHeader title="Your position" />
      <div className="flex flex-col gap-4 px-5 pb-5">
        {position.positions.map((p) => (
          <div key={p.portfolio_id}>
            <Link
              to={`/portfolios/${p.portfolio_id}`}
              className="text-[13px] font-medium text-ink transition-colors hover:text-accent"
            >
              {p.portfolio_name}
            </Link>
            <dl className="mt-2 flex flex-col gap-1.5 text-[13px]">
              <PosRow label="Lots held" value={String(p.lots)} />
              <PosRow
                label="Avg cost"
                value={fmtRp(Math.round(p.avg_cost_per_share))}
              />
              <PosRow label="Market value" value={fmtRp(p.market_value)} />
              <div className="flex items-baseline justify-between gap-4">
                <dt className="text-ink-3">Unrealized P&L</dt>
                <dd
                  className={`tnum text-right font-mono ${signClass(p.unrealized_pnl)}`}
                >
                  {fmtSignedRp(p.unrealized_pnl)}
                  <span className="ml-1.5 text-xs opacity-80">
                    {fmtPct(p.unrealized_pnl_pct, true)}
                  </span>
                </dd>
              </div>
              <PosRow
                label="Share of portfolio"
                value={fmtPct(p.pct_of_portfolio)}
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
      <dd className="tnum font-mono text-ink">{value}</dd>
    </div>
  );
}
