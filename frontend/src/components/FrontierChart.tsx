import { useMemo, useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { Frontier, FrontierPoint } from "../api/client";
import { CHART_NEUTRAL, token } from "../colors";
import { fmtPct } from "../lib/format";
import { EmptyState, ErrorNote, Panel, PanelHeader, Skeleton } from "./ui";

/** Mean-variance frontier: risk on x, expected return on y.
 *
 *  Deliberately NOT a recommendation screen. Mean-variance weights are
 *  violently sensitive to the expected-return estimate, and two years of daily
 *  closes pin that down badly — so a single "optimal portfolio" would carry
 *  far more confidence than the inputs deserve. Plotting the whole curve, with
 *  the holdings scattered around it and the real portfolio marked, shows the
 *  trade-off without pretending to resolve it.
 *
 *  The slider walks the curve rather than issuing instructions: it is the
 *  textbook's risk-tolerance parameter, and moving it is the point.
 */

function FrontierTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Record<string, unknown> }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload as {
    label?: string;
    volatility_pct: number;
    expected_return_pct: number;
    current_weight_pct?: number;
  };
  return (
    <div className="bg-panel px-3 py-2 text-[11px] ring-1 ring-ink">
      {p.label && <p className="font-medium text-ink">{p.label}</p>}
      <p className="tnum mt-0.5 text-ink-2">
        risk {fmtPct(p.volatility_pct)} · return {fmtPct(p.expected_return_pct, true)}
      </p>
      {p.current_weight_pct != null && (
        <p className="tnum mt-0.5 text-ink-3">
          you hold {fmtPct(p.current_weight_pct)}
        </p>
      )}
    </div>
  );
}

export function FrontierChart({
  frontier,
  loading,
  error,
}: {
  frontier: Frontier | null;
  loading: boolean;
  error?: string | null;
}) {
  // Index into the curve. Defaults to the far end of the risk scale only
  // once data arrives; until then there is nothing to point at.
  const [index, setIndex] = useState<number | null>(null);

  const accent = token("--color-accent", "#084d77");
  const ink = token("--color-ink", "#12161b");
  // Outline colour for the selected marker, so it separates from a
  // frontier dot underneath it.
  const panel = token("--color-panel", "#ffffff");

  const selected: FrontierPoint | null = useMemo(() => {
    if (!frontier?.curve.length) return null;
    const i = index == null ? 0 : Math.min(index, frontier.curve.length - 1);
    return frontier.curve[i];
  }, [frontier, index]);

  if (loading) {
    return (
      <Panel>
        <PanelHeader seq="04" title="Efficient frontier" />
        <Skeleton className="mt-6 h-[320px] w-full" />
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel>
        <PanelHeader seq="04" title="Efficient frontier" />
        <div className="mt-6">
          <ErrorNote message={error} />
        </div>
      </Panel>
    );
  }

  if (!frontier || frontier.curve.length === 0) {
    return (
      <Panel>
        <PanelHeader seq="04" title="Efficient frontier" />
        <EmptyState
          title="Not enough shared history"
          body={
            frontier && frontier.excluded.length > 0
              ? `Needs at least two holdings priced over the same period. ${frontier.excluded.join(", ")} ${frontier.excluded.length === 1 ? "has" : "have"} too little overlapping history.`
              : "Needs at least two holdings priced over the same period."
          }
        />
      </Panel>
    );
  }

  const curve = frontier.curve.map((p) => ({
    volatility_pct: p.volatility_pct,
    expected_return_pct: p.expected_return_pct,
  }));

  const assets = frontier.assets.map((a) => ({
    ...a,
    label: a.ticker,
  }));

  const current =
    frontier.current_volatility_pct != null &&
    frontier.current_expected_return_pct != null
      ? [
          {
            label: "Your portfolio",
            volatility_pct: frontier.current_volatility_pct,
            expected_return_pct: frontier.current_expected_return_pct,
          },
        ]
      : [];

  const marker = selected
    ? [
        {
          label: "Selected allocation",
          volatility_pct: selected.volatility_pct,
          expected_return_pct: selected.expected_return_pct,
        },
      ]
    : [];

  // Ordered by what you HOLD, not by the suggested weight.
  //
  // Sorting by the suggestion re-orders the table on every slider step, which
  // drags the "you hold" figures up and down the screen with their tickers.
  // The numbers never changed, but rows swapping under a stationary cursor is
  // indistinguishable from values changing — and it hides the one comparison
  // this table exists to make. Holdings are fixed while the slider moves, so
  // ordering by them keeps every row still and lets the allocation column be
  // the only thing that moves.
  const rows = selected
    ? Object.entries(selected.weights)
        .map(([ticker, weight]) => ({
          ticker,
          weight,
          held:
            frontier.assets.find((a) => a.ticker === ticker)?.current_weight_pct ?? 0,
        }))
        .sort((a, b) => b.held - a.held || a.ticker.localeCompare(b.ticker))
    : [];

  return (
    <Panel>
      <PanelHeader
        seq="04"
        title="Efficient frontier"
        right={
          <span className="w-wide text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
            {frontier.trading_days} shared sessions
          </span>
        }
      />

      <p className="mt-4 max-w-[68ch] text-[12px] leading-relaxed text-ink-2">
        Every allocation of your current holdings that gives the most expected
        return for its risk. Estimated from {frontier.trading_days} sessions of
        shared price history — expected returns are the least reliable part of
        this model, so read the curve, not the decimal places.
      </p>

      <div className="mt-6 h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 8 }}>
            <CartesianGrid stroke={CHART_NEUTRAL} strokeOpacity={0.18} />
            <XAxis
              type="number"
              dataKey="volatility_pct"
              name="risk"
              tick={{ fontSize: 11, fill: CHART_NEUTRAL }}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              label={{
                value: "RISK (ANNUALISED VOLATILITY)",
                position: "insideBottom",
                offset: -16,
                style: { fontSize: 10, fill: CHART_NEUTRAL, letterSpacing: "0.12em" },
              }}
            />
            <YAxis
              type="number"
              dataKey="expected_return_pct"
              name="return"
              tick={{ fontSize: 11, fill: CHART_NEUTRAL }}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            />
            <ZAxis range={[60, 60]} />
            <Tooltip content={<FrontierTooltip />} cursor={{ strokeOpacity: 0.2 }} />

            {/* The frontier. Each dot is one solved allocation, not a
                sample of a smooth function — drawing them says so, and shows
                where the sweep is dense (the curved low-risk end) versus
                sparse (the straight tail). Small and half-opaque so the line
                still reads as the shape and the selected marker still wins. */}
            <Scatter
              data={curve}
              line={{ stroke: accent, strokeWidth: 2 }}
              shape={(p: { cx?: number; cy?: number }) => (
                <circle cx={p.cx} cy={p.cy} r={2.5} fill={accent} fillOpacity={0.5} />
              )}
              isAnimationActive={false}
            />
            {/* each holding on its own — the curve is what beats them */}
            <Scatter
              data={assets}
              fill={CHART_NEUTRAL}
              shape="circle"
              isAnimationActive={false}
            />
            {/* where the portfolio actually is */}
            <Scatter
              data={current}
              fill={ink}
              shape="square"
              isAnimationActive={false}
            />
            {/* Where the slider is pointing. Drawn last so it sits above
                the curve it lives on, and outlined so it stays visible when
                it lands on top of a frontier dot. */}
            <Scatter
              data={marker}
              shape={(p: { cx?: number; cy?: number }) => {
                const x = p.cx ?? 0;
                const y = p.cy ?? 0;
                return (
                  <path
                    d={`M${x} ${y - 7}L${x + 7} ${y}L${x} ${y + 7}L${x - 7} ${y}Z`}
                    fill={accent}
                    stroke={panel}
                    strokeWidth={1.5}
                  />
                );
              }}
              isAnimationActive={false}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
        <div className="flex items-center gap-1.5">
          <span className="block h-0.5 w-4" style={{ background: accent }} />
          frontier
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="block h-2 w-2 rounded-full"
            style={{ background: CHART_NEUTRAL }}
          />
          each holding
        </div>
        <div className="flex items-center gap-1.5">
          <span className="block h-2 w-2" style={{ background: ink }} />
          your portfolio
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="block h-2 w-2 rotate-45"
            style={{ background: accent }}
          />
          slider position
        </div>
      </dl>

      {/* the risk-tolerance sweep — the textbook's tau, as a control */}
      <div className="mt-6 border-t border-line pt-5">
        <label
          htmlFor="frontier-tau"
          className="w-wide block text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3"
        >
          Risk tolerance
        </label>
        <input
          id="frontier-tau"
          type="range"
          min={0}
          max={frontier.curve.length - 1}
          value={index ?? 0}
          onChange={(e) => setIndex(Number(e.target.value))}
          className="mt-3 w-full accent-accent"
        />
        {selected && (
          <p className="tnum mt-2 text-[12px] text-ink-2">
            Risk {fmtPct(selected.volatility_pct)} · expected return{" "}
            {fmtPct(selected.expected_return_pct, true)}
          </p>
        )}
      </div>

      {rows.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[320px] text-[13px]">
            <thead>
              <tr className="border-b-2 border-ink text-left">
                <th className="px-3 py-2.5 pl-0 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                  Ticker
                </th>
                <th className="px-3 py-2.5 text-right text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                  This allocation
                </th>
                <th className="px-3 py-2.5 pr-0 text-right text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                  You hold
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.ticker} className="border-b border-line last:border-0">
                  <td className="w-wide px-3 py-2 pl-0 text-[13px] font-bold uppercase tracking-[0.06em] text-ink">
                    {r.ticker}
                  </td>
                  <td className="tnum px-3 py-2 text-right">
                    {fmtPct(r.weight)}
                  </td>
                  <td className="tnum px-3 py-2 pr-0 text-right text-ink-3">
                    {fmtPct(r.held)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {frontier.excluded.length > 0 && (
        <p className="mt-4 text-[11px] leading-relaxed text-ink-3">
          Excluded for want of overlapping price history:{" "}
          {frontier.excluded.join(", ")}.
        </p>
      )}
    </Panel>
  );
}
