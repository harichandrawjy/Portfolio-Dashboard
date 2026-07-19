import { Warning } from "@phosphor-icons/react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { Allocation } from "../api/client";
import { CHART_NEUTRAL, sectorColor } from "../colors";
import { fmtPct, fmtRp } from "../lib/format";
import { EmptyState, Panel, PanelHeader, Skeleton } from "./ui";

const MAX_SLICES = 7;

function DonutTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { label: string; value: number; pct: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-[6px] bg-panel px-3 py-2 text-xs ring-1 ring-line-2 shadow-[0_12px_32px_-12px_rgb(22_24_29/0.35)]">
      <p className="font-medium text-ink">{p.label}</p>
      <p className="tnum mt-0.5 font-mono text-ink-2">
        {fmtRp(p.value)} · {fmtPct(p.pct)}
      </p>
    </div>
  );
}

export function AllocationDonut({
  allocation,
  loading,
}: {
  allocation: Allocation | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Panel tone="flat">
        <PanelHeader title="Allocation" />
        <div className="flex flex-col items-center gap-4 px-5 pb-5">
          <Skeleton className="h-44 w-44 rounded-full" />
          <div className="w-full space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </Panel>
    );
  }

  const sectors = allocation?.by_sector ?? [];
  if (!allocation || sectors.length === 0) {
    return (
      <Panel tone="flat">
        <PanelHeader title="Allocation" />
        <EmptyState
          title="Nothing to allocate yet"
          body="The sector breakdown appears once this portfolio holds priced positions."
        />
      </Panel>
    );
  }

  const heldSectors = sectors.map((s) => s.sector);
  const top = sectors.slice(0, MAX_SLICES);
  const rest = sectors.slice(MAX_SLICES);
  const slices = top.map((s) => ({
    label: s.sector ?? "Unknown",
    value: s.market_value,
    pct: s.weight_pct,
    color: sectorColor(s.sector, heldSectors),
  }));
  if (rest.length > 0) {
    slices.push({
      label: "Other",
      value: rest.reduce((a, s) => a + s.market_value, 0),
      pct: rest.reduce((a, s) => a + s.weight_pct, 0),
      color: CHART_NEUTRAL,
    });
  }

  return (
    <Panel tone="flat">
      <PanelHeader title="Allocation" />
      <div className="px-5 pb-5">
        <div className="relative mx-auto h-48 w-48">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="label"
                innerRadius="68%"
                outerRadius="100%"
                paddingAngle={2}
                stroke="#f7f7f4"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {slices.map((s) => (
                  <Cell key={s.label} fill={s.color} />
                ))}
              </Pie>
              <Tooltip content={<DonutTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[11px] text-ink-3">Total</span>
            <span className="tnum font-mono text-[13px] font-semibold text-ink">
              {fmtRp(allocation.total_market_value)}
            </span>
          </div>
        </div>

        <ul className="mt-4 space-y-1.5">
          {slices.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-[13px]">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: s.color }}
              />
              <span className="truncate text-ink-2">{s.label}</span>
              <span className="tnum ml-auto font-mono text-ink">
                {fmtPct(s.pct)}
              </span>
            </li>
          ))}
        </ul>

        {allocation.flags.length > 0 && (
          <div className="mt-4 space-y-2">
            {allocation.flags.map((f, i) => (
              <p
                key={i}
                className="flex items-start gap-2 rounded-[8px] bg-warn/10 px-3 py-2 text-xs text-warn ring-1 ring-warn/25"
              >
                <Warning size={14} weight="light" className="mt-[1px] shrink-0" />
                <span>
                  {f.type === "stock_concentration"
                    ? `${f.ticker} is ${fmtPct(f.weight_pct)} of this portfolio (above ${f.threshold_pct}%)`
                    : `${f.sector ?? "Unknown"} sector is ${fmtPct(f.weight_pct)} of this portfolio (above ${f.threshold_pct}%)`}
                </span>
              </p>
            ))}
          </div>
        )}

        {allocation.unpriced.length > 0 && (
          <p className="mt-3 text-xs text-ink-3">
            No price yet for {allocation.unpriced.join(", ")}; excluded from the
            weights above.
          </p>
        )}
      </div>
    </Panel>
  );
}
