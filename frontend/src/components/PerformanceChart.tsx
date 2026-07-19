import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Performance, RangeKey } from "../api/client";
import { CHART_NEUTRAL, SERIES } from "../colors";
import { fmtDateShort, fmtRp, fmtRpCompact } from "../lib/format";
import { EmptyState, Panel, Segmented, Skeleton } from "./ui";

const PORTFOLIO_COLOR = SERIES[0];

const RANGES: { value: RangeKey; label: string }[] = [
  { value: "1mo", label: "1M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  const rows: Record<string, number> = {};
  for (const p of payload) rows[p.dataKey] = p.value;
  return (
    <div className="rounded-[8px] bg-panel-2 px-3 py-2 text-xs ring-1 ring-line-2 shadow-lg shadow-black/40">
      <p className="mb-1.5 font-medium text-ink-2">{fmtDateShort(label)}</p>
      <div className="flex flex-col gap-1">
        <p className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: PORTFOLIO_COLOR }}
          />
          <span className="text-ink-3">Portfolio</span>
          <span className="tnum ml-auto pl-4 font-mono text-ink">
            {fmtRp(rows.value)}
          </span>
        </p>
        {rows.ihsg != null && (
          <p className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: CHART_NEUTRAL }}
            />
            <span className="text-ink-3">IHSG</span>
            <span className="tnum ml-auto pl-4 font-mono text-ink">
              {fmtRp(rows.ihsg)}
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

function LegendChip({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-3">
      <svg width="18" height="6" aria-hidden>
        <line
          x1="0"
          y1="3"
          x2="18"
          y2="3"
          stroke={color}
          strokeWidth="2"
          strokeDasharray={dashed ? "4 3" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}

export function PerformanceChart({
  performance,
  loading,
  range,
  onRangeChange,
}: {
  performance: Performance | null;
  loading: boolean;
  range: RangeKey;
  onRangeChange: (r: RangeKey) => void;
}) {
  const points = performance?.points ?? [];
  const data = points.map((p) => ({
    date: p.date,
    value: p.portfolio_value,
    ihsg: p.ihsg_normalized,
  }));

  return (
    <Panel>
      {/* the legend IS the header — the chart needs no label */}
      <div className="flex items-center justify-between gap-4 px-5 pt-4 pb-3">
        <div className="flex items-center gap-3">
          <LegendChip color={PORTFOLIO_COLOR} label="Portfolio" />
          <LegendChip color={CHART_NEUTRAL} label="IHSG, rebased" dashed />
        </div>
        <Segmented options={RANGES} value={range} onChange={onRangeChange} />
      </div>
      <div className="px-3 pb-4">
        {loading ? (
          <Skeleton className="mx-2 h-[280px]" />
        ) : data.length === 0 ? (
          <EmptyState
            title="No performance yet"
            body="The chart appears once this portfolio has a transaction inside the selected range."
          />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
              <CartesianGrid
                vertical={false}
                stroke="rgb(255 255 255 / 0.05)"
              />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDateShort}
                stroke="transparent"
                tick={{ fill: "#5f6878", fontSize: 11 }}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis
                tickFormatter={(v: number) => fmtRpCompact(v)}
                stroke="transparent"
                tick={{ fill: "#5f6878", fontSize: 11 }}
                tickLine={false}
                width={78}
                domain={["auto", "auto"]}
              />
              <Tooltip
                content={<ChartTooltip />}
                cursor={{ stroke: "rgb(255 255 255 / 0.15)", strokeWidth: 1 }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={PORTFOLIO_COLOR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3.5, strokeWidth: 0 }}
              />
              <Line
                type="monotone"
                dataKey="ihsg"
                stroke={CHART_NEUTRAL}
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}
