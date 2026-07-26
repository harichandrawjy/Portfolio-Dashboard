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

/** The portfolio's worth is the page's headline — set in a bold cobalt
 *  block like a magazine-cover stat, with the supporting figures kept
 *  quiet on paper beside it. */
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
      <div className="grid gap-5 lg:grid-cols-[minmax(300px,0.85fr)_1.4fr]">
        <Skeleton className="h-[148px] rounded-xl" />
        <div className="flex flex-wrap items-center gap-x-12 gap-y-6 self-center">
          <Skeleton className="h-16 w-40" />
          <Skeleton className="h-16 w-40" />
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
    <div className="grid gap-5 lg:grid-cols-[minmax(300px,0.85fr)_1.4fr]">
      {/* the hero: the portfolio's worth as a bold cobalt block */}
      <div className="relative overflow-hidden rounded-xl bg-accent px-6 py-6 text-white shadow-[0_1px_2px_rgb(23_30_54/0.1),0_22px_50px_-26px_rgb(43_53_112/0.55)]">
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full opacity-70"
          viewBox="0 0 400 200"
          preserveAspectRatio="none"
          aria-hidden
        >
          <path
            d="M0 150 C 70 140 90 96 150 92 C 220 88 240 128 300 96 C 350 70 370 44 400 34"
            fill="none"
            stroke="#ffffff"
            strokeOpacity="0.22"
            strokeWidth="2"
          />
        </svg>
        <p className="relative text-[12px] uppercase tracking-[0.16em] text-white/70">
          Total value
        </p>
        <p className="tnum relative mt-2.5 font-mono text-[42px] font-semibold leading-none tracking-tight sm:text-[52px]">
          {fmtRp(totals?.market_value)}
        </p>
        <p className="tnum relative mt-3 text-xs text-white/70">
          {totals && totals.unpriced_holdings > 0
            ? `${totals.unpriced_holdings} holding(s) unpriced`
            : newestAsOf
              ? `as of ${fmtAsOf(newestAsOf)}`
              : totals?.market_value != null
                ? "at last close"
                : "no priced holdings yet"}
        </p>
      </div>

      {/* supporting figures, quiet on paper */}
      <dl className="flex flex-wrap items-center gap-x-12 gap-y-6 self-center px-1">
        <div>
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
        {totals != null && totals.realized_pnl !== 0 && (
          <div>
            <dt className="text-[13px] text-ink-3">Realized P&L</dt>
            <dd
              className={`tnum mt-1 font-mono text-xl font-semibold ${signClass(totals.realized_pnl)}`}
            >
              {fmtSignedRp(totals.realized_pnl)}
            </dd>
            <dd className="tnum mt-1 text-xs text-ink-3">locked in by sells</dd>
          </div>
        )}
        {totals?.cash_tracked && (
          <div>
            <dt className="text-[13px] text-ink-3">Cash</dt>
            <dd className="tnum mt-1 font-mono text-xl font-semibold text-ink">
              {fmtRp(totals.cash_balance)}
            </dd>
            <dd className="tnum mt-1 text-xs text-ink-3">
              deposits minus trades
            </dd>
          </div>
        )}
        <div>
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
