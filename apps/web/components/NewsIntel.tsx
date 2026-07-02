"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getNewsIntel, type NewsIntel as NewsIntelData } from "@/lib/api";

function directionBadgeClass(direction?: string) {
  if (direction === "bullish") return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
  if (direction === "bearish") return "bg-rose-500/10 text-rose-400 border border-rose-500/20";
  return "bg-neutral-500/10 text-neutral-400 border border-neutral-500/20";
}

function countdown(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  const past = ms < 0;
  const abs = Math.abs(ms);
  const h = Math.floor(abs / 3_600_000);
  const m = Math.floor((abs % 3_600_000) / 60_000);
  const rel = h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : h >= 1 ? `${h}h ${m}m` : `${m}m`;
  return past ? `${rel} ago` : `in ${rel}`;
}

export function NewsIntel({ userId }: { userId: number | null }) {
  const [data, setData] = useState<NewsIntelData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getNewsIntel(userId)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [userId]);

  useEffect(() => {
    load();
    // event windows and the live read move — refresh every 60s
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  if (error) return null; // fail quiet — don't break the page if the endpoint is unreachable
  if (!data) return null;

  const header = (
    <div className="mb-3">
      <h2 className="text-lg font-semibold text-neutral-100 flex items-center gap-2">
        News Intel
        <span className="text-[10px] uppercase tracking-wide text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-full px-2 py-0.5">
          XAU/USD · event-driven
        </span>
      </h2>
      <p className="text-xs text-neutral-500 mt-1">
        On each scheduled US macro release (NFP, CPI, FOMC…) the engine re-analyses gold and posts a read.
        The probability is anchored to this setup&apos;s real backtested hit-rate — not a marketing number —
        and every call is graded against the actual move afterward.
      </p>
    </div>
  );

  // ── locked (free plan): show only the event calendar + upsell ──
  if (data.locked) {
    const next = data.upcoming_events?.[0];
    return (
      <section className="rounded-xl p-5 border border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-neutral-900/60">
        {header}
        {next && (
          <p className="text-sm text-neutral-300">
            Next gold event: <span className="font-medium text-neutral-100">{next.name}</span>{" "}
            <span className="text-neutral-500">({countdown(next.time)})</span>
          </p>
        )}
        <Link
          href="/pricing"
          className="mt-3 inline-block rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950"
        >
          Upgrade to Pro to unlock News Intel
        </Link>
      </section>
    );
  }

  const intel = data.intel;
  const tr = data.track_record;
  const ev = intel?.event ?? data.focus_event ?? null;

  return (
    <section className="rounded-xl p-5 border border-amber-500/30 bg-gradient-to-b from-amber-500/5 to-neutral-900/60 space-y-4">
      {header}

      {ev && (
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <p className="text-sm font-semibold text-neutral-100">
              {ev.name}
              {ev.impact === "high" && (
                <span className="ml-2 text-[10px] uppercase text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded px-1.5 py-0.5">
                  high impact
                </span>
              )}
            </p>
            <p className="text-xs text-neutral-500">
              {countdown(ev.time)} · {new Date(ev.time).toLocaleString()} · {ev.source}
            </p>
          </div>
          {intel && (
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${directionBadgeClass(intel.direction)}`}>
              {intel.direction}
            </span>
          )}
        </div>
      )}

      {intel && intel.direction !== "neutral" ? (
        <>
          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-bold font-mono text-neutral-100">
              {intel.probability != null ? `${(intel.probability * 100).toFixed(0)}%` : "—"}
            </span>
            <span className="text-xs text-neutral-500">
              probability the {intel.direction} read plays out
              {intel.probability == null && " (not enough backtest history yet)"}
            </span>
          </div>

          {intel.levels && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { label: "Entry", value: intel.levels.entry, color: "text-sky-400" },
                { label: "Stop", value: intel.levels.stop_loss, color: "text-rose-400" },
                { label: "Target", value: intel.levels.take_profit, color: "text-emerald-400" },
                { label: "R:R", value: `1:${intel.levels.risk_reward}`, color: "text-neutral-100" },
              ].map((cell) => (
                <div key={cell.label} className="bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2">
                  <p className="text-[10px] text-neutral-500">{cell.label}</p>
                  <p className={`text-sm font-mono font-semibold ${cell.color}`}>{cell.value}</p>
                </div>
              ))}
            </div>
          )}

          {intel.commentary && (
            <p className="text-sm text-neutral-300 italic border-l-2 border-amber-500/40 pl-3">{intel.commentary}</p>
          )}

          <p className="text-xs text-neutral-500">
            Backtested hit-rate on this exact setup:{" "}
            <span className="font-mono text-neutral-200">
              {intel.backtest_hit_rate != null ? `${(intel.backtest_hit_rate * 100).toFixed(1)}%` : "n/a"}
            </span>{" "}
            · strategy agreement <span className="font-mono text-neutral-200">{intel.strategy_agreement}</span> · news{" "}
            <span className="font-mono text-neutral-200">{intel.news_sentiment}</span>
          </p>
        </>
      ) : (
        <p className="text-sm text-neutral-400">
          No decisive gold read right now — the strategies don&apos;t agree on a direction into this event.
          A no-trade call is a valid call.
        </p>
      )}

      {tr && tr.graded > 0 && (
        <div className="pt-2 border-t border-neutral-800 text-xs text-neutral-500">
          Track record (measured, not claimed):{" "}
          <span className="text-neutral-200 font-mono">
            {tr.hit_rate != null ? `${(tr.hit_rate * 100).toFixed(0)}% hit-rate` : "—"}
          </span>{" "}
          over {tr.hits + tr.misses} graded calls ({tr.hits} hit / {tr.misses} miss
          {tr.neutral > 0 ? ` / ${tr.neutral} flat` : ""}).
        </div>
      )}
    </section>
  );
}
