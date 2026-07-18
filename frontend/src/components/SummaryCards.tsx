import type { Holdings, Metrics } from "../api/client";
import {
  DASH,
  fmtAsOf,
  fmtPct,
  fmtRp,
  fmtSignedRp,
  signClass,
} from "../lib/format";
import { Panel, Skeleton } from "./ui";

function Card({
  label,
  value,
  valueClass = "text-ink",
  sub,
}: {
  label: string;
  value: string;
  valueClass?: string;
  sub?: string;
}) {
  return (
    <Panel className="px-5 py-4">
      <p className="text-[13px] font-medium text-ink-2">{label}</p>
      <p className={`tnum mt-1.5 font-mono text-xl font-semibold ${valueClass}`}>
        {value}
      </p>
      {sub && <p className="tnum mt-1 text-xs text-ink-3">{sub}</p>}
    </Panel>
  );
}

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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Panel key={i} className="px-5 py-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-7 w-36" />
            <Skeleton className="mt-2 h-3 w-28" />
          </Panel>
        ))}
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
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <Card
        label="Total value"
        value={fmtRp(totals?.market_value)}
        sub={
          totals && totals.unpriced_holdings > 0
            ? `${totals.unpriced_holdings} holding(s) unpriced · as of ${fmtAsOf(newestAsOf)}`
            : newestAsOf
              ? `as of ${fmtAsOf(newestAsOf)}`
              : "no priced holdings yet"
        }
      />
      <Card
        label="Unrealized P&L"
        value={fmtSignedRp(totals?.unrealized_pnl)}
        valueClass={signClass(totals?.unrealized_pnl)}
        sub={pnlPct == null ? DASH : `${fmtPct(pnlPct, true)} of cost basis`}
      />
      <Card
        label={`Return vs IHSG (${metrics?.range ?? DASH})`}
        value={
          vsIhsg == null ? DASH : `${vsIhsg > 0 ? "+" : ""}${vsIhsg.toFixed(2)} pp`
        }
        valueClass={signClass(vsIhsg)}
        sub={
          metrics && metrics.total_return_pct != null
            ? `you ${fmtPct(metrics.total_return_pct, true)} · IHSG ${fmtPct(metrics.benchmark_return_pct, true)}`
            : "appears after your first transaction"
        }
      />
    </div>
  );
}
