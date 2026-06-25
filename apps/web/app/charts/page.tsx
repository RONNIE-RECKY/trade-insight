"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { Chart } from "@/components/Chart";
import { RequireAuth } from "@/components/RequireAuth";
import {
  analyze,
  canExport,
  canUseIntradayBot,
  exportAnalysisUrl,
  getCandles,
  listSymbols,
  type Candle,
  type FullAnalysis,
} from "@/lib/api";

const TIMEFRAMES = [
  { value: "5min", label: "5M" },
  { value: "15min", label: "15M" },
  { value: "30min", label: "30M" },
  { value: "1h", label: "1H" },
  { value: "4h", label: "4H" },
  { value: "1day", label: "1D" },
];

function directionBadgeClass(direction: string) {
  if (direction === "bullish") return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
  if (direction === "bearish") return "bg-rose-500/10 text-rose-400 border border-rose-500/20";
  return "bg-neutral-500/10 text-neutral-400 border border-neutral-500/20";
}

function trendBadgeClass(trend: string) {
  if (trend === "uptrend") return "text-emerald-400";
  if (trend === "downtrend") return "text-rose-400";
  return "text-neutral-400";
}

function confidenceBadgeClass(confidence?: string) {
  if (confidence === "high") return "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30";
  if (confidence === "medium") return "bg-amber-500/10 text-amber-300 border border-amber-500/20";
  return "bg-neutral-500/10 text-neutral-400 border border-neutral-500/20";
}

function ChartsPageInner() {
  const { data: session } = useSession();
  const plan = (session?.user as { plan?: string } | undefined)?.plan;
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;
  const intradayUnlocked = canUseIntradayBot(plan);
  const exportUnlocked = canExport(plan);

  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbol, setSymbol] = useState<string>("");
  const [dataSource, setDataSource] = useState<string>("");
  const [interval, setInterval_] = useState<string>("1day");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [report, setReport] = useState<FullAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listSymbols()
      .then((res) => {
        setSymbols(res.symbols);
        setSymbol(res.symbols[0] ?? "");
        setDataSource(res.data_source);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const runAnalysis = useCallback(() => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    Promise.all([getCandles(symbol, interval), analyze(symbol, interval, userId)])
      .then(([c, r]) => {
        setCandles(c.candles);
        setReport(r);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [symbol, interval, userId]);

  // auto-run whenever symbol or timeframe changes
  useEffect(() => {
    runAnalysis();
  }, [runAnalysis]);

  const cp = report?.current_position;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <label htmlFor="symbol" className="text-sm font-medium text-neutral-400">
            Symbol
          </label>
          <select
            id="symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-neutral-900 border border-neutral-700 rounded-md px-3 py-1.5 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {dataSource === "simulated" && (
            <span
              title="No live data API key configured — prices are simulated for the demo."
              className="text-[10px] font-medium text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-full px-2 py-0.5"
            >
              simulated data
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded-md p-1">
            {TIMEFRAMES.map((tf) => {
              const locked = tf.value !== "1day" && !intradayUnlocked;
              return (
                <button
                  key={tf.value}
                  onClick={() => (locked ? null : setInterval_(tf.value))}
                  title={locked ? "Upgrade to Pro for intraday timeframes" : undefined}
                  className={`text-xs font-medium px-3 py-1 rounded ${
                    interval === tf.value
                      ? "bg-cyan-500/20 text-cyan-300"
                      : locked
                      ? "text-neutral-600 cursor-not-allowed"
                      : "text-neutral-400 hover:text-neutral-100"
                  }`}
                >
                  {tf.label}
                  {locked && <span className="ml-1 text-[9px] uppercase text-neutral-600">pro</span>}
                </button>
              );
            })}
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="rounded-md bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-1.5 text-sm font-semibold text-neutral-950 disabled:opacity-50"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </div>

      {/* Export */}
      {report && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-neutral-500">Export analysis:</span>
          {exportUnlocked ? (
            <>
              <a
                href={exportAnalysisUrl(symbol, interval, "json")}
                className="rounded-md border border-neutral-700 px-3 py-1 text-neutral-200 hover:border-neutral-500"
              >
                JSON
              </a>
              <a
                href={exportAnalysisUrl(symbol, interval, "csv")}
                className="rounded-md border border-neutral-700 px-3 py-1 text-neutral-200 hover:border-neutral-500"
              >
                CSV
              </a>
            </>
          ) : (
            <Link href="/pricing" className="text-cyan-300 underline underline-offset-2">
              Upgrade to Pro to export
            </Link>
          )}
        </div>
      )}

      {!intradayUnlocked && (
        <p className="text-xs text-cyan-300/80">
          Free plan covers daily analysis.{" "}
          <Link href="/pricing" className="underline underline-offset-2">
            Upgrade to Pro
          </Link>{" "}
          to analyze the 5M–4H timeframes.
        </p>
      )}

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-300">
          <p className="font-medium">Couldn&apos;t reach the analysis service.</p>
          <p className="mt-1 text-rose-300/80">
            Make sure the backend is running, then{" "}
            <button onClick={runAnalysis} className="underline underline-offset-2">
              retry
            </button>
            .
          </p>
        </div>
      )}

      {candles.length > 0 && (
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
          <Chart candles={candles} patterns={report?.patterns ?? []} levels={report?.levels ?? null} />
        </div>
      )}

      {report && (
        <>
          {report.commentary && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                <h2 className="font-semibold text-neutral-100">
                  Bot analysis <span className="text-neutral-500 font-normal">({interval})</span>
                </h2>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${confidenceBadgeClass(report.confidence)}`}>
                    {report.confidence ?? "low"} confidence
                  </span>
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${directionBadgeClass(report.direction)}`}>
                    {report.direction} · {report.strategy_agreement}
                  </span>
                </div>
              </div>
              <p className="text-sm text-neutral-300 italic border-l-2 border-cyan-500/40 pl-3">{report.commentary}</p>
              <p className="mt-3 text-xs text-neutral-500">
                Backtested hit-rate on this exact rule &amp; timeframe:{" "}
                <span className="font-mono text-neutral-200">
                  {report.backtest_hit_rate != null ? `${(report.backtest_hit_rate * 100).toFixed(1)}%` : "n/a"}
                </span>
                {report.high_confidence ? (
                  <span className="ml-2 text-emerald-400">meets the 80%+ high-confidence bar</span>
                ) : (
                  <span className="ml-2 text-neutral-500">below the 80% high-confidence bar — treat as lower conviction</span>
                )}
              </p>
            </div>
          )}

          {/* Strategy consensus */}
          {report.strategies && report.strategies.length > 0 && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-neutral-100">Strategy consensus</h2>
                <span className="text-xs text-neutral-400 font-mono">{report.strategy_agreement} agree</span>
              </div>
              <ul className="space-y-2">
                {report.strategies.map((s) => (
                  <li
                    key={s.name}
                    className="flex items-start justify-between gap-3 bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium text-neutral-200">{s.name}</p>
                      <p className="text-xs text-neutral-500">{s.reason}</p>
                    </div>
                    <span
                      className={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full ${directionBadgeClass(
                        s.signal
                      )}`}
                    >
                      {s.signal}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Current position */}
          {cp && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
              <h2 className="font-semibold text-neutral-100 mb-3">Current position</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                <Stat label="Price" value={cp.current_price} mono />
                <Stat label="Trend" valueNode={<span className={trendBadgeClass(cp.trend)}>{cp.trend}</span>} />
                <Stat label="Range position" value={cp.range_position_pct != null ? `${cp.range_position_pct}%` : "—"} />
                <Stat
                  label="vs EMA 20 / 50"
                  valueNode={
                    <span className="font-mono">
                      <span className={cp.above_ema_20 ? "text-emerald-400" : "text-rose-400"}>
                        {cp.above_ema_20 ? "above" : "below"}
                      </span>{" "}
                      /{" "}
                      <span className={cp.above_ema_50 ? "text-emerald-400" : "text-rose-400"}>
                        {cp.above_ema_50 ? "above" : "below"}
                      </span>
                    </span>
                  }
                />
                <Stat label="Nearest support" value={cp.nearest_support ?? "—"} mono />
                <Stat label="Nearest resistance" value={cp.nearest_resistance ?? "—"} mono />
              </div>
              {report.levels && cp.distance_to_entry_pct != null && (
                <p className="mt-3 text-xs text-neutral-500">
                  Distance to entry{" "}
                  <span className="text-neutral-300 font-mono">{cp.distance_to_entry_pct}%</span> · to stop{" "}
                  <span className="text-rose-400 font-mono">{cp.distance_to_stop_pct}%</span> · to target{" "}
                  <span className="text-emerald-400 font-mono">{cp.distance_to_target_pct}%</span>
                </p>
              )}
            </div>
          )}

          {/* Trade plan */}
          {report.levels && report.direction !== "neutral" && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
              <h2 className="font-semibold text-neutral-100 mb-3">Trade plan</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: "Entry", value: report.levels.entry, color: "text-sky-400" },
                  { label: "Stop loss", value: report.levels.stop_loss, color: "text-rose-400" },
                  { label: "Take profit", value: report.levels.take_profit, color: "text-emerald-400" },
                  { label: "Risk : Reward", value: `1 : ${report.levels.risk_reward}`, color: "text-neutral-100" },
                ].map((cell) => (
                  <div key={cell.label} className="bg-neutral-950/60 border border-neutral-800 rounded-lg p-3">
                    <p className="text-xs text-neutral-500">{cell.label}</p>
                    <p className={`text-base font-mono font-semibold ${cell.color}`}>{cell.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Chart patterns across the whole graph */}
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
            <h2 className="font-semibold text-neutral-100 mb-3">
              Chart patterns <span className="text-neutral-500 font-normal">(whole graph · {report.patterns.length})</span>
            </h2>
            {report.patterns.length === 0 ? (
              <p className="text-sm text-neutral-500">No patterns detected on this timeframe.</p>
            ) : (
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm font-mono">
                {report.patterns.map((p, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2"
                  >
                    <span className="text-neutral-200">
                      {p.pattern.replace(/_/g, " ")}{" "}
                      <span className="text-neutral-500">({p.direction})</span>
                    </span>
                    <span className="text-neutral-400">{p.points.map((pt) => pt.price.toFixed(5)).join(" → ")}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function ChartsPage() {
  return (
    <RequireAuth>
      <ChartsPageInner />
    </RequireAuth>
  );
}

function Stat({
  label,
  value,
  valueNode,
  mono,
}: {
  label: string;
  value?: string | number;
  valueNode?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="bg-neutral-950/60 border border-neutral-800 rounded-lg p-3">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className={`text-sm font-semibold text-neutral-100 ${mono ? "font-mono" : ""}`}>
        {valueNode ?? value}
      </p>
    </div>
  );
}
