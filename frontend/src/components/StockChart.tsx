import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  createChart,
  createSeriesMarkers,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import type {
  PositionTxn,
  ProvisionalBar,
  RangeKey,
  StockPricePoint,
} from "../api/client";
import { CHART_NEUTRAL, SERIES, token } from "../colors";
import { EmptyState, ErrorNote, Panel, Segmented, Skeleton } from "./ui";

const ACCENT = SERIES[0];

// The signal colours at reduced strength, for the one bar that is still
// moving. Literals rather than tokens because a canvas renderer needs a
// concrete string; they track --color-pos #126b46 and --color-neg #bc1f33.
const PROVISIONAL_POS = "rgba(18, 107, 70, 0.5)";
const PROVISIONAL_NEG = "rgba(188, 31, 51, 0.5)";

/** A drawn candle body, matching PerformanceChart's line swatches — the
 *  system draws its legend marks rather than borrowing ▲/▼ glyphs. */
function LegendSwatch({ tone, label }: { tone: "pos" | "neg"; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="7" height="12" aria-hidden className="shrink-0">
        <line
          x1="3.5" y1="0" x2="3.5" y2="12" stroke="currentColor" strokeWidth="1" className={tone === "pos" ? "text-pos" : "text-neg"}
        />
        {/* mirrors the candles, which are solid in BOTH directions — the key
            has to match the plot or it teaches the wrong thing */}
        <rect
          x="0.5" y="3" width="6" height="6" strokeWidth="1" className={
            tone === "pos"
              ? "fill-pos stroke-pos"
              : "fill-neg stroke-neg"
          }
        />
      </svg>
      {label}
    </span>
  );
}

const RANGES: { value: RangeKey; label: string }[] = [
  { value: "1mo", label: "1M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

type ChartStyle = "candles" | "line";
const STYLE_KEY = "arus.chartStyle";

/** Candlestick chart on TradingView's open-source Lightweight Charts™
 *  engine — rendering only; every bar comes from our own price_history.
 *  Native pan/zoom and crosshair; volume as a bottom histogram; the
 *  user's trades as B/S arrows at their (snapped) dates. */
export function StockChart({
  points,
  loading,
  error,
  range,
  onRangeChange,
  showIhsg,
  onToggleIhsg,
  markers,
  provisional,
  avgCost,
}: {
  points: StockPricePoint[];
  loading: boolean;
  error?: string | null;
  range: RangeKey;
  onRangeChange: (r: RangeKey) => void;
  showIhsg: boolean;
  onToggleIhsg: () => void;
  markers: PositionTxn[];
  /** Today's session so far. Real OHLC from the quote cache, never from
   *  `price_history`, which refuses to hold an unfinished session. Drawn
   *  muted so it never reads as a settled candle. */
  provisional?: ProvisionalBar | null;
  /** Share-weighted break-even for this ticker across every portfolio that
   *  holds it, fees included. Null when nothing is held. */
  avgCost?: number | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<ChartStyle>(() =>
    localStorage.getItem(STYLE_KEY) === "line" ? "line" : "candles",
  );
  const pickStyle = (s: ChartStyle) => {
    setStyle(s);
    localStorage.setItem(STYLE_KEY, s);
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el || loading || points.length === 0) return;

    // bound to the same tokens as the CSS, resolved once per chart build
    const POS = token("pos", "#126b46");
    const NEG = token("neg", "#bc1f33");
    const INK = token("ink", "#0a0c10");
    const INK_MUTED = token("ink-3", "#5c6373");

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: INK_MUTED,
        fontSize: 11,
        // Archivo, like the rest of the app. JetBrains Mono was uninstalled
        // in the redesign, so this was silently falling back to whatever
        // generic monospace the OS supplies.
        fontFamily: "'Archivo Variable', ui-sans-serif, system-ui, sans-serif",
      },
      grid: {
        vertLines: { visible: false },
        // matches the Recharts grid in PerformanceChart; the ink triplet is
        // 10 12 16 in the current system, not the retired 23 30 54
        horzLines: { color: "rgba(10, 12, 16, 0.1)" },
      },
      rightPriceScale: {
        borderVisible: false,
        // Comparing a stock against the index only means anything if both are
        // expressed as change, not as level. In Normal mode the rebased
        // benchmark is anchored to the stock's first close in the range, so
        // its height is decided by how far the stock has since travelled:
        // PANI over ALL starts at Rp 13 and ends near 19.100, which pinned
        // the benchmark to a flat line at the bottom and dragged the axis
        // through zero. Percentage mode normalises BOTH series to their first
        // visible bar, so they always start together at 0% and the comparison
        // holds for any stock over any range.
        mode: showIhsg ? PriceScaleMode.Percentage : PriceScaleMode.Normal,
      },
      timeScale: { borderVisible: false },
      crosshair: {
        horzLine: { labelBackgroundColor: INK },
        vertLine: { labelBackgroundColor: INK },
      },
      localization: {
        // The formatter is handed whatever the scale is currently measuring,
        // so it has to follow the mode. Without this branch, percentage mode
        // would render "12" where it means "+12,5%" — a number that looks
        // like a rupiah price and is wrong by three orders of magnitude.
        priceFormatter: (p: number) =>
          showIhsg
            ? `${p > 0 ? "+" : ""}${p.toLocaleString("id-ID", {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              })}%`
            : Math.round(p).toLocaleString("id-ID"),
      },
    });

    let mainSeries: ISeriesApi<"Candlestick"> | ISeriesApi<"Area">;
    if (style === "candles") {
      // Both directions are solid. Up days used to be hollow so that fill
      // carried direction alongside hue, but at one-day candle widths the
      // body is only a few pixels across, so the outline read as a thin
      // green sliver rather than as an up day. A filled body is legible at
      // that size; colour-vision redundancy is carried instead by vertical
      // position on the axis and by the signed P&L figures on the page.
      const candles = chart.addSeries(CandlestickSeries, {
        upColor: POS,
        downColor: NEG,
        wickUpColor: POS,
        wickDownColor: NEG,
        borderVisible: true,
        borderUpColor: POS,
        borderDownColor: NEG,
      });
      const bars = points.map((p) => ({
        time: p.date as Time,
        open: p.open ?? p.close,
        high: p.high ?? p.close,
        low: p.low ?? p.close,
        close: p.close,
      }));
      if (provisional) {
        // Muted, so an unfinished session cannot be read as a settled one.
        // Per-bar colours rather than a second series: a separate series would
        // get its own scale and legend entry for what is really one more bar.
        const up = provisional.close >= (provisional.open ?? provisional.close);
        const tint = up ? PROVISIONAL_POS : PROVISIONAL_NEG;
        bars.push({
          time: provisional.date as Time,
          open: provisional.open ?? provisional.close,
          high: provisional.high ?? provisional.close,
          low: provisional.low ?? provisional.close,
          close: provisional.close,
          color: tint,
          borderColor: tint,
          wickColor: tint,
        } as (typeof bars)[number]);
      }
      candles.setData(bars);
      mainSeries = candles;
    } else {
      const area = chart.addSeries(AreaSeries, {
        lineColor: ACCENT,
        lineWidth: 2,
        // the accent triplet is 8 77 119 now, not the retired indigo 43 53 112
        topColor: "rgba(8, 77, 119, 0.14)",
        bottomColor: "rgba(8, 77, 119, 0)",
        crosshairMarkerRadius: 4,
      });
      area.setData(
        points
          .map((p) => ({ time: p.date as Time, value: p.close }))
          .concat(
            provisional
              ? [{ time: provisional.date as Time, value: provisional.close }]
              : [],
          ),
      );
      mainSeries = area;
    }

    // ---- break-even -----------------------------------------------------
    // The one line here about the holder rather than the instrument:
    // everything above it is profit on this position, everything below it is
    // loss, which is the question the page is actually being opened to answer.
    //
    // Hidden with the IHSG comparison on, because that scale reads in percent
    // change, where a rupiah level is meaningless.
    //
    // There used to be a second, dotted line here titled "now", marking the
    // live quote for the window where the chart ended at the last published
    // close and could not show today. Migration 0007 put real intraday OHLC on
    // `latest_quotes`, which let the provisional candle draw that session
    // properly — and the line quietly became unreachable-when-right. It was
    // skipped whenever a provisional bar existed (redundant), which is exactly
    // when the quote is live; so the only times it rendered were the times the
    // quote was NOT newer than the last bar, i.e. stale. After the 18:30 bar
    // job it sat below a settled candle from the same day insisting it was
    // "now" — 268 against a 270 close on PACK, on 8 of 14 tickers at once.
    // The provisional bar's freshness gate in routers/securities.py is the
    // rule that was missing here; applying it would have made the line never
    // draw, so it is gone instead.
    if (!showIhsg && avgCost != null) {
      mainSeries.createPriceLine({
        price: avgCost,
        color: ACCENT,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "avg cost",
      });
    }

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "vol",
      priceFormat: { type: "volume" },
      color: "rgba(10, 12, 16, 0.15)",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    volume.setData(
      points
        .filter((p) => p.volume != null)
        .map((p) => ({ time: p.date as Time, value: p.volume! }))
        .concat(
          provisional && provisional.volume != null
            ? [{ time: provisional.date as Time, value: provisional.volume }]
            : [],
        ),
    );

    if (showIhsg) {
      const ihsg = chart.addSeries(LineSeries, {
        color: CHART_NEUTRAL,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      ihsg.setData(
        points
          .filter((p) => p.ihsg != null)
          .map((p) => ({ time: p.date as Time, value: p.ihsg! })),
      );
    }

    // trades snapped to the first plotted date on/after execution
    const seriesMarkers = markers
      .map((t): SeriesMarker<Time> | null => {
        const pt = points.find((p) => p.date >= t.executed_at);
        if (!pt) return null;
        return t.type === "BUY"
          ? {
              time: pt.date as Time,
              position: "belowBar",
              color: POS,
              shape: "arrowUp",
              text: "B",
            }
          : {
              time: pt.date as Time,
              position: "aboveBar",
              color: NEG,
              shape: "arrowDown",
              text: "S",
            };
      })
      .filter((m): m is SeriesMarker<Time> => m !== null);
    if (seriesMarkers.length > 0) createSeriesMarkers(mainSeries, seriesMarkers);

    chart.timeScale().fitContent();
    return () => chart.remove();
    // `provisional` is a dep so today's candle follows the 15-minute quote
    // refresh — it carries the live price now that the "now" line is gone.
  }, [points, loading, showIhsg, markers, style, provisional, avgCost]);

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 pb-3 pt-3 sm:px-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 className="flex items-baseline gap-3 text-[12px] font-bold uppercase leading-none tracking-[0.14em] text-ink">
            <span className="seq text-accent" aria-hidden>
              01
            </span>
            <span className="w-wide">Price</span>
          </h2>
          <div className="w-wide flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-bold uppercase tracking-[0.12em] text-ink-3">
            {style === "candles" ? (
              <>
                <LegendSwatch tone="pos" label="up day" />
                <LegendSwatch tone="neg" label="down day" />
              </>
            ) : (
              <span>daily closes</span>
            )}
            {markers.length > 0 && <span>B/S arrows mark your trades</span>}
            {/* the muted bar is the only one still moving — say so, or it
                reads as a rendering fault rather than an open session */}
            {provisional && <span className="text-accent">faded bar = today, still open</span>}
            {!showIhsg && avgCost != null && (
              <span className="text-accent">dashed = your avg cost</span>
            )}
            {/* the axis stops reading in rupiah while the comparison is on,
                so the chart says so rather than leaving the reader to notice */}
            {showIhsg && <span className="text-accent">% change from start</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            label="Chart style"
            options={[
              { value: "candles" as ChartStyle, label: "Candles" },
              { value: "line" as ChartStyle, label: "Line" },
            ]}
            value={style}
            onChange={pickStyle}
          />
          {/* selected state inverts to solid ink, matching Segmented */}
          <button
            onClick={onToggleIhsg}
            aria-pressed={showIhsg}
            className={
              "px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em] ring-1 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent " +
              (showIhsg
                ? "bg-ink text-bg ring-ink"
                : "text-ink-3 ring-line-2 hover:bg-ink hover:text-bg")
            }
          >
            vs IHSG
          </button>
          <Segmented
            label="Price range" options={RANGES}
            value={range}
            onChange={onRangeChange}
          />
        </div>
      </div>
      <div className="px-3 pb-4">
        {error ? (
          <div className="px-2 py-4">
            <ErrorNote message={error} />
          </div>
        ) : loading ? (
          <Skeleton className="mx-2 h-[320px]" />
        ) : points.length === 0 ? (
          <EmptyState
            title="No prices in this range" body="Try a wider range, or check back after the next nightly sync."
          />
        ) : (
          /* the canvas is opaque to assistive tech; name what it plots */
          <div
            ref={containerRef}
            role="img" aria-label={`${style === "candles" ? "Candlestick" : "Line"} chart of daily prices over ${
              RANGES.find((r) => r.value === range)?.label ?? range
            }${showIhsg ? ", shown as percent change from the start of the range with the IHSG benchmark overlaid" : ""}${
              markers.length > 0 ? `, marking ${markers.length} of your trades` : ""
            }. The figures below repeat this data as text.`}
            className="h-[320px] w-full"
          />
        )}
      </div>
    </Panel>
  );
}
