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

import type { Frontier, FrontierPoint, MuModel } from "../api/client";
import { CHART_NEUTRAL, token } from "../colors";
import { fmtDec, fmtPct } from "../lib/format";
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

type Mode = "explore" | "min_risk" | "target" | "max_sharpe";

const MODES: { key: Mode; label: string; hint: string }[] = [
  { key: "explore", label: "Explore", hint: "Slide along the whole frontier" },
  { key: "min_risk", label: "Min risk", hint: "Least volatility, whatever the return" },
  { key: "target", label: "Target return", hint: "Least risk that still reaches a return you name" },
  { key: "max_sharpe", label: "Max Sharpe", hint: "Best return per unit of risk" },
];

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
  targetInput,
  onTargetChange,
  muModel,
  onMuModelChange,
}: {
  frontier: Frontier | null;
  loading: boolean;
  error?: string | null;
  /** Lives in the parent because changing it refetches — the least-risk
   *  allocation for a target return is solved server-side, not interpolated
   *  from the plotted points. */
  targetInput: string;
  onTargetChange: (value: string) => void;
  /** Which expected-return model to use. Also a refetch, since mu is solved
   *  server-side and the whole curve changes with it. */
  muModel: MuModel;
  onMuModelChange: (m: MuModel) => void;
}) {
  // Index into the curve. Defaults to the far end of the risk scale only
  // once data arrives; until then there is nothing to point at.
  const [index, setIndex] = useState<number | null>(null);
  // Which of the textbook's three formulations to show. "explore" is the
  // free slider — the three named modes are fixed points on the same curve,
  // so switching between them never moves the curve itself.
  const [mode, setMode] = useState<Mode>("explore");

  const accent = token("--color-accent", "#084d77");
  const ink = token("--color-ink", "#12161b");
  // Outline colour for the selected marker, so it separates from a
  // frontier dot underneath it.
  const panel = token("--color-panel", "#ffffff");

  // In a named mode the point comes from the server's own selection, so the
  // figure shown is the exact optimum rather than the nearest grid point the
  // slider happens to land on.
  const selected: FrontierPoint | null = useMemo(() => {
    if (!frontier?.curve.length) return null;
    const named =
      mode === "min_risk"
        ? frontier.min_risk
        : mode === "max_sharpe"
          ? frontier.max_sharpe
          : mode === "target"
            ? frontier.target
            : null;
    if (named) {
      return {
        volatility_pct: named.volatility_pct,
        expected_return_pct: named.expected_return_pct,
        weights: named.weights,
      };
    }
    if (mode !== "explore") return null; // target asked for but unreachable
    const i = index == null ? 0 : Math.min(index, frontier.curve.length - 1);
    return frontier.curve[i];
  }, [frontier, index, mode]);

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
          beta: frontier.assets.find((a) => a.ticker === ticker)?.beta ?? null,
        }))
        .sort((a, b) => b.held - a.held || a.ticker.localeCompare(b.ticker))
    : [];

  // Beta is a CAPM quantity: it is what turns the market's premium into each
  // holding's expected return. Under log returns nothing is regressed against
  // the index, so the column would be a full stack of em-dashes pretending a
  // number exists. Drop it instead.
  const showBeta = frontier.mu_source === "capm";

  const namedSharpe =
    mode === "min_risk"
      ? (frontier.min_risk?.sharpe ?? null)
      : mode === "max_sharpe"
        ? (frontier.max_sharpe?.sharpe ?? null)
        : mode === "target"
          ? (frontier.target?.sharpe ?? null)
          : null;

  return (
    <Panel>
      <PanelHeader
        seq="04"
        title="Efficient frontier"
        right={
          <span className="w-wide text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
            {frontier.window_year} · {frontier.trading_days} sessions
          </span>
        }
      />

      <p className="mt-4 max-w-[68ch] text-[12px] leading-relaxed text-ink-2">
        Every allocation of your current holdings that gives the most expected
        return for its risk. Both axes are estimated from calendar{" "}
        {frontier.window_year} alone, the last complete year, which is{" "}
        {frontier.trading_days} sessions of shared price history. Expected return{" "}
        {frontier.mu_source === "capm"
          ? "comes from CAPM rather than from what each stock actually did."
          : frontier.mu_source === "log"
            ? "is each holding's own annualised log return, which prices in volatility drag but is still history."
            : "is each stock's own average return."}
      </p>

      {/* Which estimator produced the y-axis. Offered as a switch because the
          two disagree enormously and the disagreement is the lesson: CAPM
          compresses expected returns into a ~5pp band, historical log returns
          spread them over ~60pp and drive the optimum into a single holding.
          Risk is identical either way — only mu changes. */}
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span
          id="mu-model-label"
          className="w-wide text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3"
        >
          Expected return from
        </span>
        {/* An exclusive choice, so radiogroup rather than two independent
            aria-pressed toggles — it announces "1 of 2" the way the app's
            other exclusive controls do. */}
        {/* The divider is drawn ON the unselected segment, not in a gap
            between the two. The hairline bed the mode tabs use is 15% black,
            which reads against a white neighbour but is swallowed by a filled
            one — and this group has exactly ONE boundary with a filled block
            always on one side of it, so a bed could never show here. Exactly
            one segment is unselected at any time, so exactly one rule is
            drawn, always on paper. Group width is unchanged by the flip. */}
        <div
          role="radiogroup"
          aria-labelledby="mu-model-label"
          className="inline-flex max-w-full flex-wrap"
        >
          {(
            [
              ["capm", "CAPM", "Rf + β(Rm − Rf). Steadier, but assumes a market premium"],
              ["log", "Log returns", "Each holding's own annualised geometric return. Prices in volatility drag, but noisy"],
            ] as const
          ).map(([key, label, hint], i) => (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={muModel === key}
              title={hint}
              onClick={() => onMuModelChange(key)}
              className={`w-wide px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent ${
                muModel === key
                  ? "bg-accent text-on-accent"
                  : `bg-panel text-ink-2 hover:bg-panel-2 hover:text-ink border-line ${
                      i === 0 ? "border-r" : "border-l"
                    }`
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* The assumption, stated. CAPM's expected market return is a judgement
          call, and the whole model hangs off it — so it is shown next to what
          the index actually did rather than hidden in a constant. When those
          two disagree sharply, that IS the caveat. */}
      {frontier.mu_source === "capm" && (
        <dl className="tnum mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-line pt-4 text-[11px]">
          <div>
            <dt className="w-wide text-[10px] uppercase tracking-[0.12em] text-ink-3">
              Risk-free
            </dt>
            <dd className="mt-0.5 text-ink">{fmtPct(frontier.risk_free_rate_pct)}</dd>
          </div>
          <div>
            <dt className="w-wide text-[10px] uppercase tracking-[0.12em] text-ink-3">
              Assumed equity premium
            </dt>
            <dd className="mt-0.5 text-ink">
              {fmtPct(frontier.equity_risk_premium_pct)}
            </dd>
          </div>
          <div>
            <dt className="w-wide text-[10px] uppercase tracking-[0.12em] text-ink-3">
              So market is assumed to return
            </dt>
            <dd className="mt-0.5 text-ink">{fmtPct(frontier.market_return_pct)}</dd>
          </div>
          <div>
            <dt className="w-wide text-[10px] uppercase tracking-[0.12em] text-ink-3">
              IHSG actually did
            </dt>
            <dd className="mt-0.5 text-ink-2">
              {fmtPct(frontier.market_return_realised_pct, true)}
            </dd>
          </div>
        </dl>
      )}

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

      {/* The three formulations, plus the free sweep. They are selections on
          one curve rather than separate optimisations, so switching never
          moves the frontier — only the marker on it. */}
      <div className="mt-6 border-t border-line pt-5">
        {/* The hairline bed is painted by the container's OWN background, so
            any part of a row the tabs do not cover shows up as a grey block
            rather than as a 1px rule. `inline-flex` solves that for a single
            row by shrinking the container to its content — but once the row
            wraps, each line is short again and the leak returns, which on a
            375px phone left 34px of grey on the first row and 231px on the
            second.

            A 2-column grid fits the four tabs exactly, two per row, with no
            remainder for the bed to show through. Every other bed in the app
            (SummaryCards, the Portfolios figure row) stays clean because its
            cells are `flex-1` and grow to fill; that would work here too, but
            it would leave Max Sharpe spanning the full width alone. From `sm`
            the row fits on one line and the original inline-flex returns. */}
        <div
          className="grid grid-cols-2 gap-px bg-line sm:inline-flex sm:max-w-full sm:flex-wrap"
          role="tablist"
        >
          {MODES.map((m) => (
            <button
              key={m.key}
              role="tab"
              aria-selected={mode === m.key}
              title={m.hint}
              onClick={() => setMode(m.key)}
              className={`w-wide px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent ${
                mode === m.key
                  ? "bg-ink text-bg"
                  : "bg-panel text-ink-2 hover:bg-panel-2 hover:text-ink"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {mode === "explore" && (
          <div className="mt-5">
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
          </div>
        )}

        {mode === "target" && (
          <div className="mt-5">
            <label
              htmlFor="frontier-target"
              className="w-wide block text-[10px] font-bold uppercase tracking-[0.14em] text-ink-3"
            >
              Target return
            </label>
            <div className="mt-3 flex items-center gap-3">
              <input
                id="frontier-target"
                type="number"
                step="0.1"
                value={targetInput}
                onChange={(e) => onTargetChange(e.target.value)}
                className="tnum w-28 border border-line-2 bg-panel px-2 py-1.5 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
              <span className="text-[11px] text-ink-3">
                % per year
                {frontier.target_floor_pct != null &&
                  frontier.target_ceiling_pct != null && (
                    <>
                      {" · reachable "}
                      <span className="tnum">
                        {fmtPct(frontier.target_floor_pct)}
                      </span>
                      {" to "}
                      <span className="tnum">
                        {fmtPct(frontier.target_ceiling_pct)}
                      </span>
                    </>
                  )}
              </span>
            </div>
            {frontier.target == null && (
              <p className="mt-2 text-[11px] text-warn">
                Out of reach without short selling. The best your holdings can
                do is {fmtPct(frontier.target_ceiling_pct)}.
              </p>
            )}
          </div>
        )}

        {selected && (
          <p className="tnum mt-4 text-[12px] text-ink-2">
            Risk {fmtPct(selected.volatility_pct)} · expected return{" "}
            {fmtPct(selected.expected_return_pct, true)}
            {namedSharpe != null && (
              <> · Sharpe {fmtDec(namedSharpe, 3)}</>
            )}
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
                {showBeta && (
                  <th className="px-3 py-2.5 text-right text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
                    Beta
                  </th>
                )}
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
                  {showBeta && (
                    <td className="tnum px-3 py-2 text-right text-ink-3">
                      {fmtDec(r.beta)}
                    </td>
                  )}
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
