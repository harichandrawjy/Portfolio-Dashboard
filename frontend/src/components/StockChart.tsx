import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import type { PositionTxn, RangeKey, StockPricePoint } from "../api/client";
import { CHART_NEUTRAL, SERIES } from "../colors";
import { EmptyState, Panel, Segmented, Skeleton } from "./ui";

const POS = "#177245";
const NEG = "#b42332";
const INK_MUTED = "#727a8c";
const ACCENT = SERIES[0];

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

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: INK_MUTED,
        fontSize: 11,
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "rgba(23, 30, 54, 0.06)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: {
        horzLine: { labelBackgroundColor: "#1a1f2e" },
        vertLine: { labelBackgroundColor: "#1a1f2e" },
      },
      localization: {
        priceFormatter: (p: number) => Math.round(p).toLocaleString("id-ID"),
      },
    });

    let mainSeries: ISeriesApi<"Candlestick"> | ISeriesApi<"Area">;
    if (style === "candles") {
      const candles = chart.addSeries(CandlestickSeries, {
        upColor: POS,
        downColor: NEG,
        wickUpColor: POS,
        wickDownColor: NEG,
        borderVisible: false,
      });
      candles.setData(
        points.map((p) => ({
          time: p.date as Time,
          open: p.open ?? p.close,
          high: p.high ?? p.close,
          low: p.low ?? p.close,
          close: p.close,
        })),
      );
      mainSeries = candles;
    } else {
      const area = chart.addSeries(AreaSeries, {
        lineColor: ACCENT,
        lineWidth: 2,
        topColor: "rgba(43, 53, 112, 0.14)",
        bottomColor: "rgba(43, 53, 112, 0)",
        crosshairMarkerRadius: 4,
      });
      area.setData(
        points.map((p) => ({ time: p.date as Time, value: p.close })),
      );
      mainSeries = area;
    }

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "vol",
      priceFormat: { type: "volume" },
      color: "rgba(23, 30, 54, 0.12)",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    volume.setData(
      points
        .filter((p) => p.volume != null)
        .map((p) => ({ time: p.date as Time, value: p.volume! })),
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
  }, [points, loading, showIhsg, markers, style]);

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 pt-4 pb-3">
        <p className="text-xs text-ink-3">
          {style === "candles" ? (
            <>
              <span className="text-pos">▲</span> up day ·{" "}
              <span className="text-neg">▼</span> down day
            </>
          ) : (
            "daily closes"
          )}
          {markers.length > 0 && (
            <span className="ml-2">· B/S arrows mark your trades</span>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            options={[
              { value: "candles" as ChartStyle, label: "Candles" },
              { value: "line" as ChartStyle, label: "Line" },
            ]}
            value={style}
            onChange={pickStyle}
          />
          <button
            onClick={onToggleIhsg}
            aria-pressed={showIhsg}
            className={
              "rounded-full px-3 py-1 text-xs font-medium ring-1 transition-colors duration-200 " +
              (showIhsg
                ? "bg-ink/[0.07] text-ink ring-line-2"
                : "text-ink-3 ring-line hover:text-ink-2")
            }
          >
            vs IHSG
          </button>
          <Segmented options={RANGES} value={range} onChange={onRangeChange} />
        </div>
      </div>
      <div className="px-3 pb-4">
        {loading ? (
          <Skeleton className="mx-2 h-[320px]" />
        ) : points.length === 0 ? (
          <EmptyState
            title="No prices in this range"
            body="Try a wider range, or check back after the next nightly sync."
          />
        ) : (
          <div ref={containerRef} className="h-[320px] w-full" />
        )}
      </div>
    </Panel>
  );
}
