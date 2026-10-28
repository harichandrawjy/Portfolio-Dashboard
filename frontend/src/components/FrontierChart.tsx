import { useMemo, useState } from "react";
import {
  CartesianGrid,
  ReferenceLine,
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
import { fmtDec, fmtPct, fmtPctAxis } from "../lib/format";
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
 *  LAYOUT. The panel reads as one loop: the chart on the left, and beside it
 *  the control that picks a point and the mix at that point. The earlier
 *  version stacked a methodology paragraph, an estimator switch and an
 *  assumptions row ABOVE the chart, then put the controls below it and the
 *  result below those, so moving the slider changed things 400px away from
 *  your hand. The methodology is still stated in full (product principle 4),
 *  but at the foot, where it explains a result you have already seen rather
 *  than standing between you and it.
 */

/** WHY THERE IS NO "TARGET RETURN" MODE.
 *
 *  There used to be one: type a return, get the least-risky mix reaching it.
 *  It was removed because it is not a different question from "Choose risk" —
 *  the efficient frontier is monotonic, so fixing a risk and fixing a return
 *  each pin down exactly one point on the same curve. It was the same control
 *  twice, parameterised on opposite axes, and it was the only mode that could
 *  fail (an unreachable target), which bought that redundancy at the cost of
 *  an error state.
 *
 *  It also invited a precision the inputs do not have. Typing "13,5%" implies
 *  the expected return is pinned down to a tenth of a point; measured on this
 *  data it is not estimable at all (no |t| > 1.67), which is why CAPM is used
 *  for the SIGN rather than the magnitude. A number box is the wrong promise.
 *
 *  "Highest return" replaces it: the right-hand end of the curve, the mirror
 *  of "Lowest risk" at the left. The three presets are now the frontier's
 *  three canonical points — the two ends and the best trade-off between them —
 *  none of which takes input and none of which can fail. */
type Mode = "explore" | "min_risk" | "max_sharpe" | "max_return";

/** Plain names first. The hint is shown under the control, not hidden in a
 *  title attribute: "Max Sharpe" meant nothing to anyone who had not taken
 *  the course, and a tooltip on a tab is invisible on a phone. */
const MODES: { key: Mode; label: string; hint: string }[] = [
  // The hint used to read "Drag along the line" while the only control was a
  // slider in the next column — it named an affordance the chart did not have,
  // so you reached for the line and found it inert. The line is clickable now,
  // and the sentence says what both controls actually do.
  { key: "explore", label: "Choose risk", hint: "Click a point on the line, or drag the slider — from the steadiest mix to the one expected to earn most." },
  { key: "min_risk", label: "Lowest risk", hint: "The mix that swings the least, whatever it is expected to earn." },
  { key: "max_sharpe", label: "Best trade-off", hint: "The most expected return for each unit of risk taken (the highest Sharpe ratio)." },
  { key: "max_return", label: "Highest return", hint: "The far end of the line: the most these holdings can be expected to return, and what it costs in risk." },
];

/** An axis that starts and ends on round numbers just outside the data.
 *  Both axes used to start at zero, which squeezed every point into the top
 *  right corner and left the frontier a short smudge. */
function niceAxis(values: number[], floorAtZero: boolean) {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const step = span <= 8 ? 2 : span <= 20 ? 5 : span <= 60 ? 10 : 20;
  const pad = span * 0.08;
  let from = Math.floor((lo - pad) / step) * step;
  if (floorAtZero) from = Math.max(0, from);
  const to = Math.ceil((hi + pad) / step) * step;
  const ticks: number[] = [];
  for (let v = from; v <= to + 1e-9; v += step) ticks.push(Math.round(v * 100) / 100);
  return { domain: [from, to] as [number, number], ticks };
}

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
    <div className="bg-panel px-3 py-2 text-[12px] ring-1 ring-ink">
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

/** One figure in the readout, with where your own portfolio stands beneath
 *  it, so the comparison is made for you rather than across the chart. */
function Readout({
  label,
  value,
  yours,
}: {
  label: string;
  value: string;
  yours?: string;
}) {
  return (
    <div className="flex-1 basis-[120px] bg-bg py-3 pr-3 [&+&]:pl-3">
      <dt className="w-wide text-[11px] font-bold uppercase tracking-[0.14em] text-ink-3">
        {label}
      </dt>
      <dd className="tnum mt-2 whitespace-nowrap text-[22px] font-bold leading-none text-ink">
        {value}
      </dd>
      {yours && (
        <dd className="tnum mt-1.5 text-[12px] leading-tight text-ink-3">
          yours {yours}
        </dd>
      )}
    </div>
  );
}

export function FrontierChart({
  frontier,
  loading,
  error,
  muModel,
  onMuModelChange,
}: {
  frontier: Frontier | null;
  loading: boolean;
  error?: string | null;
  /** Which expected-return model to use. A refetch, since mu is solved
   *  server-side and the whole curve changes with it. */
  muModel: MuModel;
  onMuModelChange: (m: MuModel) => void;
}) {
  // Index into the curve. Starts at the low-risk end; until data arrives
  // there is nothing to point at.
  const [index, setIndex] = useState<number | null>(null);
  // Which of the textbook's three formulations to show. "explore" is the
  // free slider — the three named modes are fixed points on the same curve,
  // so switching between them never moves the curve itself.
  const [mode, setMode] = useState<Mode>("explore");

  const accent = token("accent", "#084d77");
  const ink = token("ink", "#0a0c10");
  const inkMuted = token("ink-2", "#3a4150");
  // Outline colour for the selected marker, so it separates from a
  // frontier dot underneath it.
  const panel = token("panel", "#ffffff");

  // In a named mode the point comes from the server's own selection, so the
  // figure shown is the exact optimum rather than the nearest grid point the
  // slider happens to land on.
  const selected: FrontierPoint | null = useMemo(() => {
    if (!frontier?.curve.length) return null;
    // Highest return is read off the curve's own far end rather than asked
    // for separately: the server already solved it as the last grid point, so
    // there is nothing to request and nothing that can come back unreachable.
    const named =
      mode === "min_risk"
        ? frontier.min_risk
        : mode === "max_sharpe"
          ? frontier.max_sharpe
          : mode === "max_return"
            ? frontier.curve[frontier.curve.length - 1]
            : null;
    if (named) {
      return {
        volatility_pct: named.volatility_pct,
        expected_return_pct: named.expected_return_pct,
        weights: named.weights,
      };
    }
    if (mode !== "explore") return null;
    const i = index == null ? 0 : Math.min(index, frontier.curve.length - 1);
    return frontier.curve[i];
  }, [frontier, index, mode]);

  if (loading) {
    return (
      <Panel>
        <PanelHeader seq="04" title="Efficient frontier" />
        <Skeleton className="mt-6 h-[420px] w-full" />
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

  // `i` rides along so a click on the line can select that exact solved
  // allocation rather than the nearest one by pixel distance.
  const curve = frontier.curve.map((p, i) => ({
    i,
    volatility_pct: p.volatility_pct,
    expected_return_pct: p.expected_return_pct,
  }));

  const assets = frontier.assets.map((a) => ({
    ...a,
    label: a.ticker,
  }));

  const hasCurrent =
    frontier.current_volatility_pct != null &&
    frontier.current_expected_return_pct != null;
  const current = hasCurrent
    ? [
        {
          label: "Your portfolio",
          volatility_pct: frontier.current_volatility_pct as number,
          expected_return_pct: frontier.current_expected_return_pct as number,
        },
      ]
    : [];

  const marker = selected
    ? [
        {
          label: "Selected mix",
          volatility_pct: selected.volatility_pct,
          expected_return_pct: selected.expected_return_pct,
        },
      ]
    : [];

  // THE AXES ARE FITTED TO THE DECISION SURFACE, NOT TO EVERY MARK.
  //
  // They used to be fitted to `[...curve, ...assets, ...current]`, which let
  // one wild holding set the scale for everything. With KETR at 110% risk and
  // the frontier spanning 51–72%, the curve was squeezed into ~26% of the
  // x-range and ~27% of the y-range — roughly 7% of the plot area — and the
  // other 93% was empty paper held open for three grey dots.
  //
  // That is the SAME failure the zero-anchored axes had (see `niceAxis`),
  // arriving by a different route, so the rule is now explicit: **the frontier
  // and your own portfolio set the scale**, because those are what the reader
  // is choosing between. A holding that falls outside is named underneath the
  // chart instead of bending the picture to fit it — which states the point
  // better than a dot in the corner did, since what makes those holdings
  // interesting is precisely that they are dominated.
  const scalePoints = [...curve, ...current, ...marker];
  const xAxis = niceAxis(scalePoints.map((p) => p.volatility_pct), true);
  const yAxis = niceAxis(scalePoints.map((p) => p.expected_return_pct), false);

  const onScale = (p: { volatility_pct: number; expected_return_pct: number }) =>
    p.volatility_pct >= xAxis.domain[0] &&
    p.volatility_pct <= xAxis.domain[1] &&
    p.expected_return_pct >= yAxis.domain[0] &&
    p.expected_return_pct <= yAxis.domain[1];

  const assetsOnScale = assets.filter(onScale);
  const assetsOffScale = assets.filter((a) => !onScale(a));

  // The one comparison this whole panel exists to make. Four numbers in two
  // columns left the reader to work out that a mix beat theirs on BOTH axes;
  // when it does, say so in a sentence.
  const beatsYours =
    selected && hasCurrent
      ? selected.expected_return_pct >
          (frontier.current_expected_return_pct as number) &&
        selected.volatility_pct < (frontier.current_volatility_pct as number)
      : false;

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
        .map(([ticker, weight]) => {
          const held =
            frontier.assets.find((a) => a.ticker === ticker)?.current_weight_pct ?? 0;
          return { ticker, weight, held, change: weight - held };
        })
        .sort((a, b) => b.held - a.held || a.ticker.localeCompare(b.ticker))
    : [];

  // Beta is a CAPM quantity: it is what turns the market's premium into each
  // holding's expected return. It belongs with the assumptions that explain
  // the y-axis, not in the table of mixes, and under log returns nothing is
  // regressed against the index so there is nothing to show.
  const betas =
    frontier.mu_source === "capm"
      ? frontier.assets.filter((a) => a.beta != null)
      : [];

  // Highest return has no server-sent Sharpe — it is a curve point, not one of
  // the solved Selections — so it is computed here from the same definition
  // and the same risk-free rate the server used, keeping all three presets
  // reporting the figure rather than two of them.
  const namedSharpe =
    mode === "min_risk"
      ? (frontier.min_risk?.sharpe ?? null)
      : mode === "max_sharpe"
        ? (frontier.max_sharpe?.sharpe ?? null)
        : mode === "max_return" && selected && selected.volatility_pct > 0
          ? (selected.expected_return_pct - frontier.risk_free_rate_pct) /
            selected.volatility_pct
          : null;

  const activeMode = MODES.find((m) => m.key === mode)!;
  const slider = index ?? 0;
  const sliderMax = frontier.curve.length - 1;

  return (
    <Panel>
      <PanelHeader seq="04" title="Efficient frontier" />

      <p className="mt-4 max-w-[64ch] text-[14px] leading-relaxed text-ink-2">
        Each point on the line is a way of splitting your money between the
        stocks you already hold, chosen to get the most expected return for its
        level of risk. Pick a point to see how that mix compares with yours.
      </p>

      <div className="mt-6 grid gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        {/* ── The picture ─────────────────────────────────────────────
            Sticky beside the table: a portfolio of eight holdings makes the
            table run well past the chart, and the point of reading a row is
            to see where that mix sits. Clears the 52px masthead. */}
        <div className="min-w-0 lg:sticky lg:top-[72px] lg:self-start">
          {/* Both axes are percentages, so a near-square plot reads true. At
              360px in this column the box was ~1.7:1, which visually flattens
              the slope of the curve — and that slope IS the judgement being
              asked for. */}
          <div className="h-[420px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 24, bottom: 28, left: 12 }}>
                <CartesianGrid stroke={CHART_NEUTRAL} strokeOpacity={0.18} />
                <XAxis
                  type="number"
                  dataKey="volatility_pct"
                  name="risk"
                  domain={xAxis.domain}
                  ticks={xAxis.ticks}
                  tick={{ fontSize: 12, fill: CHART_NEUTRAL }}
                  tickFormatter={(v: number) => `${v}%`}
                  label={{
                    value: "RISK · HOW MUCH IT SWINGS IN A YEAR",
                    position: "insideBottom",
                    offset: -16,
                    style: { fontSize: 11, fill: CHART_NEUTRAL, letterSpacing: "0.12em" },
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="expected_return_pct"
                  name="return"
                  domain={yAxis.domain}
                  ticks={yAxis.ticks}
                  width={56}
                  tick={{ fontSize: 12, fill: CHART_NEUTRAL }}
                  tickFormatter={(v: number) => fmtPctAxis(v)}
                  label={{
                    value: "EXPECTED RETURN A YEAR",
                    angle: -90,
                    position: "insideLeft",
                    offset: 0,
                    style: {
                      fontSize: 11,
                      fill: CHART_NEUTRAL,
                      letterSpacing: "0.12em",
                      textAnchor: "middle",
                    },
                  }}
                />
                <ZAxis range={[60, 60]} />
                <Tooltip content={<FrontierTooltip />} cursor={{ strokeOpacity: 0.2 }} />

                {/* The frontier. Each dot is one solved allocation, not a
                    sample of a smooth function — drawing them says so, and
                    shows where the sweep is dense (the curved low-risk end)
                    versus sparse (the straight tail). Small and half-opaque so
                    the line still reads as the shape and the selected marker
                    still wins. */}
                {/* THE COMPARISON, DRAWN. Your portfolio and the mix you have
                    picked were two unconnected marks on an empty plot, leaving
                    the reader to pair them by eye and then work out which way
                    each axis had moved. A hairline between them is the whole
                    argument of this panel in one stroke. Dashed and quiet: it
                    is a relationship, not a series. */}
                {hasCurrent && marker.length > 0 && (
                  <ReferenceLine
                    segment={[
                      {
                        x: frontier.current_volatility_pct as number,
                        y: frontier.current_expected_return_pct as number,
                      },
                      {
                        x: marker[0].volatility_pct,
                        y: marker[0].expected_return_pct,
                      },
                    ]}
                    stroke={ink}
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    strokeOpacity={0.45}
                    ifOverflow="hidden"
                  />
                )}
                <Scatter
                  data={curve}
                  line={{ stroke: accent, strokeWidth: 2 }}
                  cursor={mode === "explore" ? "pointer" : undefined}
                  onClick={(p: unknown) => {
                    if (mode !== "explore") return;
                    const d = p as { i?: number; payload?: { i?: number } };
                    const i = d?.i ?? d?.payload?.i;
                    if (typeof i === "number") setIndex(i);
                  }}
                  shape={(p: { cx?: number; cy?: number }) => (
                    <g>
                      {/* A 2.5px dot is not a target. This invisible disc
                          gives the click somewhere to land without changing
                          anything about how the curve is drawn. */}
                      <circle cx={p.cx} cy={p.cy} r={11} fill="transparent" />
                      <circle cx={p.cx} cy={p.cy} r={2.5} fill={accent} fillOpacity={0.5} />
                    </g>
                  )}
                  isAnimationActive={false}
                />
                {/* Each holding on its own, named where it sits. A legend
                    entry saying "each holding" over three identical grey dots
                    left you to guess which was which. */}
                <Scatter
                  data={assetsOnScale}
                  shape={(p: { cx?: number; cy?: number; payload?: { label?: string } }) => (
                    <g>
                      <circle cx={p.cx} cy={p.cy} r={4} fill={CHART_NEUTRAL} />
                      <text
                        x={(p.cx ?? 0) + 8}
                        y={(p.cy ?? 0) + 3.5}
                        fontSize={11}
                        fontWeight={700}
                        letterSpacing="0.06em"
                        fill={inkMuted}
                      >
                        {p.payload?.label}
                      </text>
                    </g>
                  )}
                  isAnimationActive={false}
                />
                {/* where the portfolio actually is */}
                <Scatter
                  data={current}
                  shape={(p: { cx?: number; cy?: number }) => (
                    <g>
                      <rect x={(p.cx ?? 0) - 4.5} y={(p.cy ?? 0) - 4.5} width={9} height={9} fill={ink} />
                      <text
                        x={(p.cx ?? 0) + 9}
                        y={(p.cy ?? 0) + 3.5}
                        fontSize={11}
                        fontWeight={700}
                        letterSpacing="0.12em"
                        fill={ink}
                      >
                        YOU
                      </text>
                    </g>
                  )}
                  isAnimationActive={false}
                />
                {/* The selected mix. Drawn last so it sits above the curve it
                    lives on, and outlined so it stays visible when it lands on
                    top of a frontier dot. */}
                <Scatter
                  data={marker}
                  shape={(p: { cx?: number; cy?: number }) => {
                    const x = p.cx ?? 0;
                    const y = p.cy ?? 0;
                    return (
                      <path
                        d={`M${x} ${y - 8}L${x + 8} ${y}L${x} ${y + 8}L${x - 8} ${y}Z`}
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

          <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3">
            <div className="flex items-center gap-1.5">
              <span className="block h-0.5 w-4" style={{ background: accent }} />
              best possible mixes
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="block h-2.5 w-2.5 rotate-45 scale-75"
                style={{ background: accent }}
              />
              selected mix
            </div>
            <div className="flex items-center gap-1.5">
              <span className="block h-2 w-2" style={{ background: ink }} />
              your portfolio
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="block h-2 w-2 rounded-full"
                style={{ background: CHART_NEUTRAL }}
              />
              one stock alone
            </div>
          </dl>

          {/* Nothing vanishes silently. A holding too wild to share the
              frontier's scale is named here with where it actually sits,
              which tells the reader more than a dot pinned into the corner
              of a distorted plot ever did.

              Separated by middots, with the units named once in the lead-in
              rather than after every figure. Commas are DECIMAL separators in
              id-ID, so a comma-joined list reads as one unbroken run of
              digits — the separator has to be something a number cannot
              contain. */}
          {assetsOffScale.length > 0 && (
            <p className="mt-2 text-[12px] leading-relaxed text-ink-3">
              Off this scale, held alone — risk / return:{" "}
              {assetsOffScale.map((a, i) => (
                <span key={a.ticker}>
                  {i > 0 && " · "}
                  <span className="w-wide font-bold uppercase tracking-[0.06em] text-ink-2">
                    {a.ticker}
                  </span>{" "}
                  <span className="tnum">
                    {fmtPct(a.volatility_pct)} / {fmtPct(a.expected_return_pct, true)}
                  </span>
                </span>
              ))}
              . Outside the range the line covers.
            </p>
          )}
        </div>

        {/* ── Pick a point, read the mix ─────────────────────────────── */}
        <div className="min-w-0">
          {/* The ways to pick a point. They are selections on one curve rather
              than separate optimisations, so switching never moves the
              frontier, only the marker on it.

              DELIBERATELY NOT A 2×2 GRID. Four equal cells in two rows read as
              two crossed dimensions, and there is only one here — worse, the
              four are not peers: "Choose risk" is the manual mode you drive
              yourself, the other three jump to a point the server computed.
              A full-width row over a row of three presets states that 1+3
              shape instead of flattening it.

              `flex-1` on the presets is load-bearing, not styling: the last
              row always grows to fill the measure, so the hairline bed is only
              ever visible as the 1px gaps it is meant to be (DESIGN.md — the
              bed must flex, not sit in fixed tracks). */}
          <div className="flex flex-wrap gap-px bg-line" role="tablist" aria-label="How to pick a point">
            {MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                role="tab"
                aria-selected={mode === m.key}
                onClick={() => setMode(m.key)}
                className={`w-wide px-3 py-2.5 text-left text-[11px] font-bold uppercase tracking-[0.12em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent ${
                  m.key === "explore" ? "basis-full" : "flex-1 basis-[104px]"
                } ${
                  mode === m.key
                    ? "bg-ink text-bg"
                    : "bg-panel text-ink-2 hover:bg-panel-2 hover:text-ink"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="mt-3 min-h-[2lh] text-[13px] leading-relaxed text-ink-3">
            {activeMode.hint}
          </p>

          {mode === "explore" && (
            <div className="mt-4">
              <label htmlFor="frontier-tau" className="sr-only">
                Position along the line, from lowest risk to highest expected return
              </label>
              <input
                id="frontier-tau"
                type="range"
                className="lot-slider"
                min={0}
                max={sliderMax}
                value={slider}
                onChange={(e) => setIndex(Number(e.target.value))}
                style={
                  {
                    "--fill": `${sliderMax > 0 ? (slider / sliderMax) * 100 : 0}%`,
                  } as React.CSSProperties
                }
              />
              <div className="mt-2 flex justify-between text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3">
                <span>Steadier</span>
                <span>Higher return</span>
              </div>
            </div>
          )}

          {selected && (
            <>
              <dl className="mt-6 flex flex-wrap gap-px border-t border-line-2 bg-line">
                <Readout
                  label="Expected return"
                  value={fmtPct(selected.expected_return_pct, true)}
                  yours={hasCurrent ? fmtPct(frontier.current_expected_return_pct, true) : undefined}
                />
                <Readout
                  label="Risk"
                  value={fmtPct(selected.volatility_pct)}
                  yours={hasCurrent ? fmtPct(frontier.current_volatility_pct) : undefined}
                />
              </dl>
              {/* THE HEADLINE, STATED. A mix that wins on BOTH axes is the
                  most useful thing this panel can tell anyone, and it was
                  being left as an exercise: four figures in two columns, and
                  you worked out the domination yourself. Not coloured — green
                  and red are the sign of a financial value and this is
                  neither — so it is ruled in accent instead, the same device
                  the page close uses. */}
              {beatsYours && (
                <p className="mt-3 border-l-[3px] border-accent pl-3 text-[13px] leading-relaxed text-ink-2">
                  This mix is expected to earn{" "}
                  <span className="font-semibold text-ink">more</span> than
                  yours while swinging{" "}
                  <span className="font-semibold text-ink">less</span> — your
                  portfolio sits below the line.
                </p>
              )}
              {/* A line, not a third figure: three cells in this column
                  squeezed "Expected return" onto two lines, and Sharpe is the
                  textbook's score for the mix rather than something you read
                  off it. */}
              {namedSharpe != null && (
                <p className="tnum mt-1 text-[13px] text-ink-3">
                  Sharpe ratio {fmtDec(namedSharpe, 2)}: expected return above
                  the risk-free rate, per unit of risk.
                </p>
              )}

              <table className="mt-4 w-full text-[14px]">
                <thead>
                  <tr className="border-b-2 border-ink text-left">
                    <th className="py-2.5 pr-3 text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3">
                      Stock
                    </th>
                    <th className="px-3 py-2.5 text-right text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3">
                      You hold
                    </th>
                    <th className="px-3 py-2.5 text-right text-[11px] font-bold uppercase tracking-[0.12em] text-ink">
                      This mix
                    </th>
                    <th className="py-2.5 pl-3 text-right text-[11px] font-bold uppercase tracking-[0.12em] text-ink-3">
                      Change
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.ticker} className="border-b border-line last:border-0">
                      <td className="w-wide py-2 pr-3 text-[14px] font-bold uppercase tracking-[0.06em] text-ink">
                        {r.ticker}
                      </td>
                      <td className="tnum px-3 py-2 text-right text-ink-3">
                        {fmtPct(r.held)}
                      </td>
                      <td className="tnum px-3 py-2 text-right font-bold text-ink">
                        {fmtPct(r.weight)}
                      </td>
                      {/* A change of weight is not a gain or a loss, so it
                          stays ink: green and red mean the sign of money. */}
                      <td
                        className={`tnum py-2 pl-3 text-right ${
                          Math.abs(r.change) < 0.005 ? "text-ink-3" : "text-ink-2"
                        }`}
                      >
                        {Math.abs(r.change) < 0.005 ? "no change" : fmtPct(r.change, true)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>

      {/* ── How the numbers are made ───────────────────────────────────
          Every assumption is still on the page. It is placed after the
          result because it explains the result, and a reader who wants to
          use the chart should not have to get through it first. */}
      <div className="mt-10 border-t border-line pt-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h4
            id="mu-model-label"
            className="w-wide text-[11px] font-bold uppercase tracking-[0.14em] text-ink-3"
          >
            How expected return is estimated
          </h4>
          {/* Offered as a switch because the two disagree enormously and the
              disagreement is the lesson: CAPM compresses expected returns
              into a ~5pp band, historical log returns spread them over ~60pp
              and drive the optimum into a single holding. Risk is identical
              either way — only mu changes.

              An exclusive choice, so radiogroup rather than two independent
              aria-pressed toggles. The divider is drawn ON the unselected
              segment: this group has exactly one boundary, with a filled
              block always on one side of it, so a hairline bed would be
              swallowed by the fill. */}
          <div
            role="radiogroup"
            aria-labelledby="mu-model-label"
            className="inline-flex max-w-full flex-wrap"
          >
            {(
              [
                ["capm", "CAPM"],
                ["log", "Past returns"],
              ] as const
            ).map(([key, label], i) => (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={muModel === key}
                onClick={() => onMuModelChange(key)}
                className={`w-wide px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-[0.12em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent ${
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

        <p className="mt-3 max-w-[72ch] text-[13px] leading-relaxed text-ink-3">
          Both axes are measured over calendar {frontier.window_year}, the last
          complete year: <span className="tnum">{frontier.trading_days}</span>{" "}
          sessions in which every holding has a price.{" "}
          {frontier.mu_source === "capm"
            ? "Expected return comes from CAPM: what the market is assumed to return, scaled by how strongly each stock moves with the IHSG (its beta). It does not use what each stock actually did."
            : frontier.mu_source === "log"
              ? "Expected return is what each holding actually returned over that year, annualised. That is honest about volatility drag, but one year of history is a noisy guide to the next."
              : "Expected return is each stock's own average return over that year."}
        </p>

        {/* The assumption, stated. CAPM's expected market return is a
            judgement call, and the whole model hangs off it — so it is shown
            next to what the index actually did rather than hidden in a
            constant. When those two disagree sharply, that IS the caveat. */}
        {frontier.mu_source === "capm" && (
          <dl className="tnum mt-4 flex flex-wrap gap-x-8 gap-y-3 text-[13px]">
            <div>
              <dt className="w-wide text-[11px] uppercase tracking-[0.12em] text-ink-3">
                Risk-free rate
              </dt>
              <dd className="mt-1 text-ink">{fmtPct(frontier.risk_free_rate_pct)}</dd>
            </div>
            <div>
              <dt className="w-wide text-[11px] uppercase tracking-[0.12em] text-ink-3">
                Assumed equity premium
              </dt>
              <dd className="mt-1 text-ink">{fmtPct(frontier.equity_risk_premium_pct)}</dd>
            </div>
            <div>
              <dt className="w-wide text-[11px] uppercase tracking-[0.12em] text-ink-3">
                So the market is assumed to return
              </dt>
              <dd className="mt-1 text-ink">{fmtPct(frontier.market_return_pct)}</dd>
            </div>
            <div>
              <dt className="w-wide text-[11px] uppercase tracking-[0.12em] text-ink-3">
                IHSG actually did
              </dt>
              <dd className="mt-1 text-ink-2">
                {fmtPct(frontier.market_return_realised_pct, true)}
              </dd>
            </div>
            {betas.length > 0 && (
              <div>
                <dt className="w-wide text-[11px] uppercase tracking-[0.12em] text-ink-3">
                  Beta against IHSG
                </dt>
                <dd className="mt-1 text-ink">
                  {betas.map((a, i) => (
                    <span key={a.ticker}>
                      {i > 0 && <span className="text-ink-3"> · </span>}
                      <span className="w-wide font-bold uppercase tracking-[0.06em]">
                        {a.ticker}
                      </span>{" "}
                      {fmtDec(a.beta)}
                    </span>
                  ))}
                </dd>
              </div>
            )}
          </dl>
        )}

        {frontier.excluded.length > 0 && (
          <p className="mt-4 text-[13px] leading-relaxed text-ink-3">
            Left out for want of overlapping price history:{" "}
            {frontier.excluded.join(", ")}.
          </p>
        )}
      </div>
    </Panel>
  );
}
