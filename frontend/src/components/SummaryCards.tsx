import type { Holdings, Metrics } from "../api/client";
import {
  DASH,
  fmtAsOf,
  fmtPct,
  fmtRp,
  fmtSignedRp,
  signClass,
} from "../lib/format";
import { Skeleton } from "./ui";

/** Unboxed hero band: the portfolio's worth is the page's headline, not a
 *  card among equals. Secondary stats hang off it behind hairlines. */
export function SummaryCards({
  holdings,
  metrics,
  loading,
}: {
  holdings: Holdings | null;
  metrics: Metrics | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-6 border-b border-line pb-6">
        <div>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-3 h-12 w-72" />
          <Skeleton className="mt-3 h-3 w-40" />
        </div>
        <div className="flex gap-10">
          <Skeleton className="h-16 w-36" />
          <Skeleton className="h-16 w-36" />
        </div>
      </div>
    );
  }

  const totals = holdings?.totals;
  const newestAsOf = holdings?.holdings.reduce<string | null>(
    (acc, h) => (h.as_of && (!acc || h.as_of > acc) ? h.as_of : acc),
    null,
  );
  const pnlPct =
    totals && totals.unrealized_pnl != null && totals.cost_basis > 0
      ? (totals.unrealized_pnl / totals.cost_basis) * 100
      : null;
  const vsIhsg =
    metrics &&
    metrics.total_return_pct != null &&
    metrics.benchmark_return_pct != null
      ? metrics.total_return_pct - metrics.benchmark_return_pct
      : null;

  return (
    <div className="flex flex-wrap items-end justify-between gap-x-10 gap-y-6 border-b border-line pb-6">
      <div>
        <p className="text-[13px] text-ink-3">Total value</p>
        <p className="tnum mt-1 font-mono text-[42px] font-semibold leading-none tracking-tight text-ink sm:text-[52px]">
          {fmtRp(totals?.market_value)}
        </p>
        <p className="tnum mt-2.5 text-xs text-ink-3">
          {totals && totals.unpriced_holdings > 0
            ? `${totals.unpriced_holdings} holding(s) unpriced`
            : newestAsOf
              ? `as of ${fmtAsOf(newestAsOf)}`
              : totals?.market_value != null
                ? "at last close"
                : "no priced holdings yet"}
        </p>
      </div>

      <dl className="flex divide-x divide-line">
        <div className="pr-8 sm:pr-10">
          <dt className="text-[13px] text-ink-3">Unrealized P&L</dt>
          <dd
            className={`tnum mt-1 font-mono text-xl font-semibold ${signClass(totals?.unrealized_pnl)}`}
          >
            {fmtSignedRp(totals?.unrealized_pnl)}
          </dd>
          <dd className="tnum mt-1 text-xs text-ink-3">
            {pnlPct == null ? DASH : `${fmtPct(pnlPct, true)} of cost basis`}
          </dd>
        </div>
        {totals?.cash_tracked && (
          <div className="px-8 sm:px-10">
            <dt className="text-[13px] text-ink-3">Cash</dt>
            <dd className="tnum mt-1 font-mono text-xl font-semibold text-ink">
              {fmtRp(totals.cash_balance)}
            </dd>
            <dd className="tnum mt-1 text-xs text-ink-3">
              deposits minus trades
            </dd>
          </div>
        )}
        <div className="pl-8 sm:pl-10">
          <dt className="text-[13px] text-ink-3">
            vs IHSG <span className="text-ink-3/70">({metrics?.range ?? DASH})</span>
          </dt>
          <dd
            className={`tnum mt-1 font-mono text-xl font-semibold ${signClass(vsIhsg)}`}
          >
            {vsIhsg == null
              ? DASH
              : `${vsIhsg > 0 ? "+" : ""}${vsIhsg.toFixed(2)} pp`}
          </dd>
          <dd className="tnum mt-1 text-xs text-ink-3">
            {metrics && metrics.total_return_pct != null
              ? `you ${fmtPct(metrics.total_return_pct, true)} · IHSG ${fmtPct(metrics.benchmark_return_pct, true)}`
              : "appears after your first transaction"}
          </dd>
        </div>
      </dl>
    </div>
  );
}
