import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PositionTxn, RangeKey, StockPricePoint } from "../api/client";
import { CHART_NEUTRAL, SERIES } from "../colors";
import { fmtDateShort, fmtNumCompact, fmtRp, fmtRpCompact } from "../lib/format";
import { EmptyState, Panel, PanelHeader, Segmented, Skeleton } from "./ui";

const PRICE_COLOR = SERIES[0];
const POS = "#45c486";
const NEG = "#e5636e";

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
  showIhsg,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number }[];
  label?: string;
  showIhsg: boolean;
}) {
  if (!active || !payload?.length || !label) return null;
  const rows: Record<string, number> = {};
  for (const p of payload) rows[p.dataKey] = p.value;
  return (
    <div className="rounded-[8px] bg-panel-2 px-3 py-2 text-xs ring-1 ring-line-2 shadow-lg shadow-black/40">
      <p className="mb-1 font-medium text-ink-2">{fmtDateShort(label)}</p>
      <p className="tnum font-mono text-ink">{fmtRp(rows.close)}</p>
      {showIhsg && rows.ihsg != null && (
        <p className="tnum font-mono text-ink-3">IHSG {fmtRp(rows.ihsg)}</p>
      )}
      {rows.volume != null && (
        <p className="tnum mt-0.5 text-ink-3">vol {fmtNumCompact(rows.volume)}</p>
      )}
    </div>
  );
}

export function StockChart({
  points,
  loading,
  range,
  onRangeChange,
  showIhsg,
  onToggleIhsg,
  markers,
}: {
  points: StockPricePoint[];
  loading: boolean;
  range: RangeKey;
  onRangeChange: (r: RangeKey) => void;
  showIhsg: boolean;
  onToggleIhsg: () => void;
  markers: PositionTxn[];
}) {
  // Snap each of the user's trades to the first plotted date on/after its
  // execution date so weekend entries still land on the chart.
  const markerDots = markers
    .map((t) => {
      const point = points.find((p) => p.date >= t.executed_at);
      return point ? { x: point.date, y: t.price_per_share, type: t.type } : null;
    })
    .filter((m): m is { x: string; y: number; type: "BUY" | "SELL" } => m !== null);

  return (
    <Panel>
      <PanelHeader
        title="Price"
        right={
          <div className="flex items-center gap-3">
            <button
              onClick={onToggleIhsg}
              aria-pressed={showIhsg}
              className={
                "rounded-full px-3 py-1 text-xs font-medium ring-1 transition-colors duration-200 " +
                (showIhsg
                  ? "bg-white/10 text-ink ring-line-2"
                  : "text-ink-3 ring-line hover:text-ink-2")
              }
            >
              vs IHSG
            </button>
            <Segmented options={RANGES} value={range} onChange={onRangeChange} />
          </div>
        }
      />
      <div className="px-3 pb-4">
        {loading ? (
          <Skeleton className="mx-2 h-[300px]" />
        ) : points.length === 0 ? (
          <EmptyState
            title="No prices in this range"
            body="Try a wider range, or check back after the next nightly sync."
          />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart
              data={points}
              margin={{ top: 8, right: 12, left: 4, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="rgb(255 255 255 / 0.05)" />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDateShort}
                stroke="transparent"
                tick={{ fill: "#5f6878", fontSize: 11 }}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis
                yAxisId="price"
                tickFormatter={(v: number) => fmtRpCompact(v)}
                stroke="transparent"
                tick={{ fill: "#5f6878", fontSize: 11 }}
                tickLine={false}
                width={72}
                domain={["auto", "auto"]}
              />
              {/* volume lives on a hidden axis, bars capped to the bottom quarter */}
              <YAxis
                yAxisId="vol"
                hide
                domain={[0, (dataMax: number) => dataMax * 4]}
              />
              <Tooltip
                content={<ChartTooltip showIhsg={showIhsg} />}
                cursor={{ stroke: "rgb(255 255 255 / 0.15)", strokeWidth: 1 }}
              />
              <Bar
                yAxisId="vol"
                dataKey="volume"
                fill="rgb(255 255 255 / 0.07)"
                isAnimationActive={false}
              />
              {showIhsg && (
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="ihsg"
                  stroke={CHART_NEUTRAL}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  dot={false}
                  activeDot={{ r: 3, strokeWidth: 0 }}
                />
              )}
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="close"
                stroke={PRICE_COLOR}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3.5, strokeWidth: 0 }}
              />
              {markerDots.map((m, i) => (
                <ReferenceDot
                  key={i}
                  yAxisId="price"
                  x={m.x}
                  y={m.y}
                  r={4.5}
                  fill={m.type === "BUY" ? POS : NEG}
                  stroke="#11151d"
                  strokeWidth={2}
                  ifOverflow="extendDomain"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
        {markerDots.length > 0 && (
          <p className="mt-1 px-2 text-xs text-ink-3">
            <span className="text-pos">●</span> your buys ·{" "}
            <span className="text-neg">●</span> your sells, plotted at trade
            price
          </p>
        )}
      </div>
    </Panel>
  );
}
