"use client";

import { memo, useEffect, useRef } from "react";

// Our symbol -> TradingView symbol. FX + gold via FOREXCOM (matches the
// widget TradingView generates for XAUUSD), crypto via Bitstamp.
const TV_SYMBOL: Record<string, string> = {
  EURUSD: "FOREXCOM:EURUSD",
  GBPUSD: "FOREXCOM:GBPUSD",
  USDJPY: "FOREXCOM:USDJPY",
  USDCHF: "FOREXCOM:USDCHF",
  AUDUSD: "FOREXCOM:AUDUSD",
  USDCAD: "FOREXCOM:USDCAD",
  NZDUSD: "FOREXCOM:NZDUSD",
  XAUUSD: "FOREXCOM:XAUUSD",
  BTCUSD: "BITSTAMP:BTCUSD",
  ETHUSD: "BITSTAMP:ETHUSD",
};

// our interval -> TradingView interval
const TV_INTERVAL: Record<string, string> = {
  "5min": "5",
  "15min": "15",
  "30min": "30",
  "1h": "60",
  "4h": "240",
  "1day": "D",
};

function TradingViewChartInner({ symbol, interval }: { symbol: string; interval: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.innerHTML = ""; // drop the previous widget before mounting a new one

    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    widget.style.height = "100%";
    widget.style.width = "100%";
    container.appendChild(widget);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      allow_symbol_change: false,
      calendar: false,
      hide_side_toolbar: true,
      hide_top_toolbar: false,
      hide_legend: false,
      hide_volume: false,
      interval: TV_INTERVAL[interval] ?? "60",
      locale: "en",
      save_image: true,
      style: "1",
      symbol: TV_SYMBOL[symbol] ?? `FOREXCOM:${symbol}`,
      theme: "dark",
      timezone: "Etc/UTC",
      backgroundColor: "#0d1117", // match the site's chart surface
      gridColor: "rgba(242, 242, 242, 0.06)",
      withdateranges: false,
      studies: [],
      autosize: true,
    });
    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [symbol, interval]);

  // The embed script rewrites the widget container's inline styles, so the
  // fixed height lives on an outer wrapper — with autosize the widget then
  // fills it instead of collapsing to its ~150px minimum.
  return (
    <div style={{ height: 420, width: "100%" }}>
      <div className="tradingview-widget-container" style={{ height: "100%", width: "100%" }} ref={containerRef} />
    </div>
  );
}

// memo: only remount the (heavy) embed when symbol/interval actually change
export const TradingViewChart = memo(TradingViewChartInner);
