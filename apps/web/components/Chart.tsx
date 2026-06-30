"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Candle, LivePrice, Pattern, TradeLevels } from "@/lib/api";

type Props = {
  candles: Candle[];
  patterns: Pattern[];
  levels?: TradeLevels | null;
  livePrice?: LivePrice | null;
};

// pandas serializes datetimes as "2026-06-29 04:00:00+00:00" (space separator).
// Date.parse requires ISO 8601 with a T — normalise before parsing.
function parseTs(ts: string): UTCTimestamp {
  return (Date.parse(ts.replace(" ", "T")) / 1000) as UTCTimestamp;
}

export function Chart({ candles, patterns, levels, livePrice }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  // track extra series added per render so we can remove them before re-adding
  const extraSeriesRef = useRef<ISeriesApi<"Line">[]>([]);

  // ── mount/unmount: create chart + candlestick series once ──────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#0d1117" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "#1c2330" }, horzLines: { color: "#1c2330" } },
      width: containerRef.current.clientWidth,
      height: 420,
      timeScale: { timeVisible: true, borderColor: "#1c2330" },
      rightPriceScale: { borderColor: "#1c2330" },
    });
    chartRef.current = chart;

    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#fb7185",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#fb7185",
    });

    const handleResize = () => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      extraSeriesRef.current = []; // these belonged to the now-disposed chart
    };
  }, []);

  // ── on new candle/pattern/level data: update series data ──────────────────
  useEffect(() => {
    const series = candleSeriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart || candles.length === 0) return;

    // remove old pattern lines and price lines
    for (const s of extraSeriesRef.current) {
      try {
        chart.removeSeries(s);
      } catch {
        // already removed (e.g. chart was disposed/recreated)
      }
    }
    extraSeriesRef.current = [];

    series.setData(
      candles.map((c) => ({
        time: parseTs(c.ts),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    const lastTs = parseTs(candles[candles.length - 1].ts);

    for (const pattern of patterns) {
      if (pattern.points.length < 1) continue;
      const color =
        pattern.direction === "bullish"
          ? "#34d399"
          : pattern.direction === "bearish"
          ? "#fb7185"
          : "#818cf8";

      const pts = pattern.points
        .map((p) => ({ time: parseTs(p.ts), value: p.price }))
        .filter((p) => !isNaN(p.time));
      if (pts.length === 0) continue;

      const lineSeries = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        pointMarkersVisible: true,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      extraSeriesRef.current.push(lineSeries);

      if (pattern.points.length === 1) {
        const p = pts[0];
        // extend a horizontal line from the pattern point to the last candle
        const data = p.time < lastTs
          ? [p, { time: lastTs, value: p.value }]
          : [p];
        lineSeries.setData(data);
      } else {
        lineSeries.setData(pts);
      }
    }

    if (levels) {
      series.createPriceLine({ price: levels.entry, color: "#38bdf8", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "Entry" });
      series.createPriceLine({ price: levels.stop_loss, color: "#fb7185", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "SL" });
      series.createPriceLine({ price: levels.take_profit, color: "#34d399", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "TP" });
    }

    chart.timeScale().fitContent();
  }, [candles, patterns, levels]);

  // ── on each live-price tick: patch the last bar in place (no recreation) ──
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series || !livePrice || candles.length === 0) return;
    const last = candles[candles.length - 1];
    const t = parseTs(last.ts);
    if (!isFinite(t) || last.open == null || last.high == null || last.low == null) return;
    try {
      series.update({
        time: t,
        open: last.open,
        high: Math.max(last.high, livePrice.price),
        low: Math.min(last.low, livePrice.price),
        close: livePrice.price,
      });
    } catch {
      // lightweight-charts may throw on edge cases (e.g. update time precedes last bar)
    }
  }, [livePrice, candles]);

  return <div ref={containerRef} className="w-full" />;
}
