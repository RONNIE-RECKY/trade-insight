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
import type { Candle, Pattern, TradeLevels } from "@/lib/api";

type Props = {
  candles: Candle[];
  patterns: Pattern[];
  levels?: TradeLevels | null;
};

export function Chart({ candles, patterns, levels }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

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

    const candleSeries: ISeriesApi<"Candlestick"> = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#fb7185",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#fb7185",
    });

    candleSeries.setData(
      candles.map((c) => ({
        time: (Date.parse(c.ts) / 1000) as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    for (const pattern of patterns) {
      if (pattern.points.length < 1) continue;
      const color = pattern.direction === "bullish" ? "#34d399" : pattern.direction === "bearish" ? "#fb7185" : "#818cf8";
      const lineSeries: ISeriesApi<"Line"> = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        pointMarkersVisible: true,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      if (pattern.points.length === 1) {
        const p = pattern.points[0];
        const t = (Date.parse(p.ts) / 1000) as UTCTimestamp;
        lineSeries.setData(
          candles
            .filter((c) => (Date.parse(c.ts) / 1000) as UTCTimestamp >= t)
            .map(() => ({ time: t, value: p.price }))
            .slice(0, 1)
            .concat([{ time: ((Date.parse(candles[candles.length - 1].ts) / 1000) as UTCTimestamp), value: p.price }])
        );
      } else {
        lineSeries.setData(
          pattern.points.map((p) => ({ time: (Date.parse(p.ts) / 1000) as UTCTimestamp, value: p.price }))
        );
      }
    }

    if (levels) {
      candleSeries.createPriceLine({
        price: levels.entry,
        color: "#38bdf8",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Entry",
      });
      candleSeries.createPriceLine({
        price: levels.stop_loss,
        color: "#fb7185",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "SL",
      });
      candleSeries.createPriceLine({
        price: levels.take_profit,
        color: "#34d399",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "TP",
      });
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [candles, patterns, levels]);

  return <div ref={containerRef} className="w-full" />;
}
