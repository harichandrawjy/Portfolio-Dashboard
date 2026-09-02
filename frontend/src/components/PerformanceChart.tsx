import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Performance, RangeKey } from "../api/client";
import { CHART_NEUTRAL, SERIES, token } from "../colors";
import { fmtDateShort, fmtPct, fmtPctAxis } from "../lib/format";
import { EmptyState, ErrorNote, Panel, Segmented, Skeleton } from "./ui";

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
    <div className="bg-panel px-3 py-2 text-[11px] ring-1 ring-ink">
      <p className="w-wide mb-2 text-[10px] font-bold uppercase tracking-[0.12em] text-ink">
        {fmtDateShort(label)}
      </p>
      <div className="flex flex-col gap-1">
        <p className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2" style={{ background: PORTFOLIO_COLOR }}
          />
          <span className="text-ink-3">Portfolio</span>
          <span className="tnum ml-auto pl-4 text-ink">
            {fmtPct(rows.value, true)}
          </span>
        </p>
        {rows.ihsg != null && (
          <p className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2" style={{ background: CHART_NEUTRAL }}
            />
            <span className="text-ink-3">IHSG</span>
            <span className="tnum ml-auto pl-4 text-ink">
              {fmtPct(rows.ihsg, true)}
            </span>
          </p>
        )}
      </div>
    </div>
  );
}

function LegendChip({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="w-wide flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
      <svg width="18" height="6" aria-hidden>
        <line
          x1="0" y1="3" x2="18" y2="3" stroke={color}
          strokeWidth="3" strokeDasharray={dashed ? "4 3" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}

export function PerformanceChart({
  performance,
  loading,
  error,
  range,
  onRangeChange,
}: {
  performance: Performance | null;
  loading: boolean;
  error?: string | null;
  range: RangeKey;
  onRangeChange: (r: RangeKey) => void;
}) {
  const points = performance?.points ?? [];
  // Cumulative return, both legs, both starting at 0 on the first day of the
  // range. Nothing is rescaled to anything: two percentages share one axis
  // because they are the same quantity. The rupiah the portfolio is worth is
  // the largest figure on the page already, in the summary above.
  const data = points.map((p) => ({
    date: p.date,
    value: p.return_pct,
    ihsg: p.ihsg_return_pct,
  }));

  // A line needs two points. With one — a portfolio funded and traded on the
  // same day — Recharts drew a lone dot adrift in a year of whitespace and a
  // Y axis that repeated the same figure five times, which reads as broken
  // rather than as early. The Portfolios card already applies this rule
  // (`curve.length >= 2`); this brings the detail page in line with it.
  const singlePoint = data.length === 1;

  // Below about five points the measurements are worth marking individually:
  // an isolated vertex with `dot={false}` is invisible, so an early portfolio
  // looks like it has no data rather than a little.
  const sparse = data.length <= 5;

  // A flat series collapses the Y domain — min === max makes Recharts print
  // one tick value down the whole axis. This is NOT only a first-run problem:
  // any stretch without price movement reproduces it. Pad by a fixed
  // percentage point rather than a proportion of the value, which was safe
  // while these were rupiah and is not now: 2% of a negative return inverts
  // the domain, and 2% of a flat 0% is still 0%.
  const plotted = data
    .flatMap((d) => [d.value, d.ihsg])
    .filter((v): v is number => typeof v === "number");
  const lo = plotted.length ? Math.min(...plotted) : 0;
  const hi = plotted.length ? Math.max(...plotted) : 0;
  const yDomain: [number | string, number | string] =
    plotted.length > 0 && lo === hi ? [lo - 1, hi + 1] : ["auto", "auto"];

  return (
    <Panel>
      {/* the sequence number carries the section; the legend rides with it so
          the chart still needs no separate label */}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 pb-3 pt-3 sm:px-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 className="flex items-baseline gap-3 text-[12px] font-bold uppercase leading-none tracking-[0.14em] text-ink">
            <span className="seq text-accent" aria-hidden>
              01
            </span>
            <span className="w-wide">Performance</span>
          </h2>
          <LegendChip color={PORTFOLIO_COLOR} label="Portfolio" />
          <LegendChip color={CHART_NEUTRAL} label="IHSG" dashed />
        </div>
        <Segmented
          label="Performance range" options={RANGES}
          value={range}
          onChange={onRangeChange}
        />
      </div>
      <div className="px-3 pb-4">
        {error ? (
          <div className="px-2 py-4">
            <ErrorNote message={error} />
          </div>
        ) : loading ? (
          <Skeleton className="mx-2 h-[280px]" />
        ) : data.length === 0 ? (
          <EmptyState
            title="No performance yet" body="The chart appears once this portfolio has a transaction inside the selected range."
          />
        ) : singlePoint ? (
          // One day recorded: a return needs two closes, so there is no
          // figure to state yet. Say what unlocks the line rather than
          // drawing a chart that cannot mean anything.
          <div className="flex flex-col items-start gap-3 px-4 py-12 sm:px-5">
            <p className="w-wide text-[13px] font-bold uppercase tracking-[0.12em] text-ink">
              One day recorded
            </p>
            <p className="w-wide text-[10px] font-bold uppercase leading-none tracking-[0.14em] text-ink-3">
              {fmtDateShort(data[0].date)}
            </p>
            <p className="max-w-[46ch] text-[13px] leading-relaxed text-ink-2">
              A return is measured between two closes, so the line appears
              after the next one. Widen the range if this portfolio has older
              transactions.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="rgb(10 12 16 / 0.1)" />
              {/* break-even. On a return chart zero is the line that matters
                  and it is not one of the grid's — darker than a gridline,
                  lighter than a series, drawn under both. */}
              <ReferenceLine y={0} stroke="rgb(10 12 16 / 0.32)" strokeWidth={1} />
              <XAxis
                dataKey="date" tickFormatter={fmtDateShort}
                stroke="transparent" tick={{ fill: token("ink-3", "#5c6373"), fontSize: 10 }}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis
                tickFormatter={fmtPctAxis}
                stroke="transparent" tick={{ fill: token("ink-3", "#5c6373"), fontSize: 10 }}
                tickLine={false}
                width={56}
                domain={yDomain}
              />
              <Tooltip
                content={<ChartTooltip />}
                cursor={{ stroke: "rgb(10 12 16 / 0.45)", strokeWidth: 1 }}
              />
              {/* linear, not monotone: a spline invents curvature between two
                  closes that never happened, and the hard polyline matches the
                  measured-mark language the rest of the system uses

                  isAnimationActive={false} is deliberate and load-bearing.
                  Recharts defaults to a 1500ms draw on an `ease` curve, which
                  replayed in full every time this mounted AND every time the
                  range changed — so switching 1Y→6M to compare two periods
                  meant waiting a second and a half to read the answer. Five
                  times the 300ms ceiling for routine UI, on the most-looked-at
                  figure in the app, with an ease-in phase delaying exactly the
                  moment you are watching. AllocationDonut already opts out;
                  this makes the two charts agree. */}
              <Line
                type="linear" dataKey="value" stroke={PORTFOLIO_COLOR}
                strokeWidth={2}
                // marked only while the series is short enough that the
                // individual measurements still carry information
                dot={sparse ? { r: 2.5, strokeWidth: 0, fill: PORTFOLIO_COLOR } : false}
                isAnimationActive={false}
                activeDot={{ r: 3.5, strokeWidth: 0 }}
              />
              <Line
                type="linear" dataKey="ihsg" stroke={CHART_NEUTRAL}
                strokeWidth={2}
                strokeDasharray="5 4" dot={false}
                isAnimationActive={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}
