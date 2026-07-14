"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import {
  canSeePremiumSignals,
  getSignalOfTheDay,
  getSignalsHistory,
  getSignalsToday,
  isFreePlan,
  type Signal,
} from "@/lib/api";
import { RequireAuth } from "@/components/RequireAuth";
import { NewsIntel } from "@/components/NewsIntel";

function directionBadgeClass(direction: string) {
  if (direction === "bullish") return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
  if (direction === "bearish") return "bg-rose-500/10 text-rose-400 border border-rose-500/20";
  return "bg-neutral-500/10 text-neutral-400 border border-neutral-500/20";
}

const TF_LABEL: Record<string, string> = {
  "5min": "5M",
  "15min": "15M",
  "30min": "30M",
  "1h": "1H",
  "4h": "4H",
  "1day": "1D",
};

const TF_MINUTES: Record<string, number> = {
  "5min": 5, "15min": 15, "30min": 30, "1h": 60, "4h": 240, "1day": 1440,
};

function SignalAge({ generatedAt, interval }: { generatedAt?: string | null; interval?: string }) {
  if (!generatedAt) return null;
  const ageMins = Math.floor((Date.now() - new Date(generatedAt + "Z").getTime()) / 60_000);
  const periodMins = interval ? (TF_MINUTES[interval] ?? 1440) : 1440;
  const fresh = ageMins < periodMins;
  const label = ageMins < 1 ? "just now" : ageMins < 60 ? `${ageMins}m ago` : `${Math.floor(ageMins / 60)}h ${ageMins % 60}m ago`;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
      fresh ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/10" : "text-amber-400 border-amber-500/20 bg-amber-500/10"
    }`}>
      {label}
    </span>
  );
}

function SignalCard({
  signal,
  locked,
  lockMessage,
  lockCta,
}: {
  signal: Signal;
  locked?: boolean;
  lockMessage?: string;
  lockCta?: string;
}) {
  const isPremium = signal.tier === "premium";
  if (locked) {
    return (
      <div className="relative rounded-xl p-5 border border-cyan-500/30 bg-gradient-to-b from-cyan-500/5 to-neutral-900/60 overflow-hidden">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-neutral-100 flex items-center gap-2">
            {signal.symbol}
            {signal.interval && (
              <span className="text-[10px] font-mono text-neutral-400 bg-neutral-800 rounded px-1.5 py-0.5">
                {TF_LABEL[signal.interval] ?? signal.interval}
              </span>
            )}
            <span className="text-[10px] text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 rounded px-1.5 py-0.5">
              premium
            </span>
          </h3>
          <span className="text-[10px] uppercase tracking-wide text-neutral-500 border border-neutral-700 rounded px-1.5 py-0.5">
            locked
          </span>
        </div>
        <div className="mt-6 mb-2 text-center">
          <p className="text-sm text-neutral-300">{lockMessage ?? "Premium signal — entry, stop, target & reasoning"}</p>
          <Link
            href="/pricing"
            className="mt-3 inline-block rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950"
          >
            {lockCta ?? "Upgrade to Ultimate to unlock"}
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div
      className={`rounded-xl p-5 space-y-3 border ${
        signal.already_executed
          ? "border-neutral-800 bg-neutral-900/30 opacity-60"
          : isPremium
          ? "border-cyan-500/40 bg-gradient-to-b from-cyan-500/5 to-neutral-900/60"
          : "border-neutral-800 bg-neutral-900/60"
      }`}
    >
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-semibold text-neutral-100 flex items-center gap-2">
          {signal.symbol}
          {signal.interval && (
            <span className="text-[10px] font-mono text-neutral-400 bg-neutral-800 rounded px-1.5 py-0.5">
              {TF_LABEL[signal.interval] ?? signal.interval}
            </span>
          )}
          {isPremium && (
            <span className="text-[10px] text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 rounded px-1.5 py-0.5">
              premium
            </span>
          )}
          <SignalAge generatedAt={signal.generated_at} interval={signal.interval} />
          {signal.already_executed && (
            <span
              title="Your auto-trade bot already opened a position from this signal — it won't be reused."
              className="text-[10px] text-neutral-400 bg-neutral-800 border border-neutral-700 rounded px-1.5 py-0.5"
            >
              already executed
            </span>
          )}
        </h3>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${directionBadgeClass(signal.direction)}`}>
          {signal.direction} · conf {signal.confluence_score}
        </span>
      </div>

      {signal.entry != null && signal.stop_loss != null && signal.take_profit != null && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: "Entry", value: signal.entry, color: "text-sky-400" },
            { label: "Stop", value: signal.stop_loss, color: "text-rose-400" },
            { label: "Target", value: signal.take_profit, color: "text-emerald-400" },
            { label: "R:R", value: `1:${signal.risk_reward}`, color: "text-neutral-100" },
          ].map((cell) => (
            <div key={cell.label} className="bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2">
              <p className="text-[10px] text-neutral-500">{cell.label}</p>
              <p className={`text-sm font-mono font-semibold ${cell.color}`}>{cell.value}</p>
            </div>
          ))}
        </div>
      )}

      {signal.reasoning.commentary && (
        <p className="text-sm text-neutral-300 italic border-l-2 border-cyan-500/40 pl-3">
          {signal.reasoning.commentary}
        </p>
      )}

      <p className="text-sm text-neutral-400">
        Backtested hit-rate (this rule, this timeframe):{" "}
        <span className="font-medium text-neutral-100">
          {signal.backtest_hit_rate != null ? `${(signal.backtest_hit_rate * 100).toFixed(1)}%` : "not enough history yet"}
        </span>
      </p>

      <div>
        <h4 className="text-sm font-medium text-neutral-300 mb-1">Why this fired</h4>
        <ul className="list-disc list-inside text-sm text-neutral-300">
          {signal.reasoning.factors.map((f) => (
            <li key={f}>{f.replace(/_/g, " ")}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function SignalsPageInner() {
  const { data: session } = useSession();
  const plan = (session?.user as { plan?: string } | undefined)?.plan;
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;
  const premiumUnlocked = canSeePremiumSignals(plan);
  const free = isFreePlan(plan) || !session?.user;

  const [today, setToday] = useState<Signal[]>([]);
  const [history, setHistory] = useState<Signal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [premiumOnly, setPremiumOnly] = useState(false);
  const [sotd, setSotd] = useState<Signal | null>(null);
  const [sotdLocked, setSotdLocked] = useState(false);

  const loadSignals = useCallback(() => {
    // free is locked to gold (XAU/USD) — the backend enforces this too
    getSignalsToday(userId, free ? "XAUUSD" : undefined)
      .then((t) => setToday(t.signals))
      .catch((e) => setError(String(e)));
    if (!free) {
      getSignalsHistory(userId)
        .then((h) => setHistory(h.signals))
        .catch(() => {});
    } else {
      setHistory([]);
    }
    getSignalOfTheDay(userId)
      .then((r) => {
        setSotd(r.signal);
        setSotdLocked(r.locked);
      })
      .catch(() => {});
  }, [userId, free]);

  useEffect(() => {
    loadSignals();
    // keep "today's signal" feed live — refresh every 2 minutes in the background
    const id = setInterval(loadSignals, 120_000);
    return () => clearInterval(id);
  }, [loadSignals]);

  const HIDE_EXECUTED_AFTER = 30 * 60 * 1000; // 30 minutes
  const visibleToday = useMemo(() => {
    const now = Date.now();
    const active = today.filter((s) => {
      if (!s.already_executed) return true;
      if (!s.executed_at) return true; // show briefly if no timestamp yet
      return now - new Date(s.executed_at).getTime() < HIDE_EXECUTED_AFTER;
    });
    return premiumOnly ? active.filter((s) => s.tier === "premium") : active;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [today, premiumOnly]);
  const premiumCount = today.filter((s) => s.tier === "premium").length;

  const sotdSection = sotd && (
    <section>
      <div className="mb-3">
        <h2 className="text-lg font-semibold text-neutral-100 flex items-center gap-2">
          Signal of the day
          <span className="text-[10px] uppercase tracking-wide text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-full px-2 py-0.5">
            best across all markets &amp; timeframes
          </span>
        </h2>
        <p className="text-xs text-neutral-500 mt-1">
          The single highest-scoring setup found today — any symbol, any timeframe — ranked by its own
          backtested hit-rate, multi-timeframe/news agreement, and the adaptive learning weight of the
          strategies behind it. Not a separate guess; the same honest numbers shown below, just ranked.
        </p>
      </div>
      <SignalCard
        signal={sotd}
        locked={sotdLocked}
        lockMessage="Signal of the Day is a paying-plan feature — entry, stop, target & reasoning"
        lockCta="Upgrade to Pro to unlock"
      />
    </section>
  );

  if (free) {
    return (
      <div className="space-y-6">
        <NewsIntel userId={userId} />
        {sotdSection}
        <div>
          <h2 className="text-lg font-semibold text-neutral-100">
            Your daily gold signal <span className="text-neutral-500 font-normal">— XAU/USD</span>
          </h2>
          <p className="text-xs text-neutral-500 mt-1">
            Free plan: one daily XAU/USD (gold) signal.{" "}
            <Link href="/pricing" className="text-cyan-300 underline underline-offset-2">
              Upgrade
            </Link>{" "}
            for all 10 markets, every timeframe, premium signals and high-confidence (80%+ backtested) highlights.
          </p>
        </div>

        {error && <p className="text-rose-400 text-sm">{error}</p>}
        {today.length === 0 ? (
          <p className="text-sm text-neutral-500">
            No qualifying daily gold signal right now — check back later.
          </p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {today.map((s) => (
              <SignalCard key={s.id} signal={s} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <NewsIntel userId={userId} />
      {sotdSection}
      <section>
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div>
            <h2 className="text-lg font-semibold text-neutral-100">
              Today&apos;s signals{" "}
              <span className="text-neutral-500 font-normal">
                ({today.length} total · {premiumCount} premium)
              </span>
            </h2>
            <p className="text-xs text-neutral-500 mt-1">
              Each signal refreshes on its own candle period — a 30M signal updates every 30 minutes, a 1H
              every hour, and so on. Premium = 1h/4h/daily all agree and news doesn&apos;t contradict. Each shows
              its own real backtested hit-rate.
            </p>
          </div>
          <div className="flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded-md p-1">
            <button
              onClick={() => setPremiumOnly(false)}
              className={`text-xs font-medium px-3 py-1 rounded ${
                !premiumOnly ? "bg-cyan-500/20 text-cyan-300" : "text-neutral-400 hover:text-neutral-100"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setPremiumOnly(true)}
              className={`text-xs font-medium px-3 py-1 rounded ${
                premiumOnly ? "bg-cyan-500/20 text-cyan-300" : "text-neutral-400 hover:text-neutral-100"
              }`}
            >
              Premium
            </button>
          </div>
        </div>

        {!premiumUnlocked && premiumCount > 0 && (
          <p className="text-xs text-cyan-300/80 mb-3">
            {premiumCount} premium signals today are locked on your plan.{" "}
            <Link href="/pricing" className="underline underline-offset-2">
              Upgrade to unlock
            </Link>
            .
          </p>
        )}

        {error && <p className="text-rose-400 text-sm">{error}</p>}
        {visibleToday.length === 0 && !error && (
          <p className="text-sm text-neutral-500">No qualifying setups in this view.</p>
        )}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {visibleToday.map((s) => (
            <SignalCard key={s.id} signal={s} locked={s.tier === "premium" && !premiumUnlocked} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100 mb-3">History</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {history.map((s) => (
            <SignalCard key={s.id} signal={s} locked={s.tier === "premium" && !premiumUnlocked} />
          ))}
        </div>
      </section>
    </div>
  );
}

export default function SignalsPage() {
  return (
    <RequireAuth>
      <SignalsPageInner />
    </RequireAuth>
  );
}
