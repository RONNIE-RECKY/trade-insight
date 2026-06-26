"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { getAdminOverview, getAdminSignals, getAdminUsers, getLearningStats, type AdminOverview, type AdminUser, type Signal, type StrategyWeight } from "@/lib/api";

// Admin console at an unlisted path (no nav link) + server-side is_admin check.
export default function ControlPage() {
  const { data: session, status } = useSession();
  const isAdmin = Boolean((session?.user as { isAdmin?: boolean } | undefined)?.isAdmin);
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [learning, setLearning] = useState<StrategyWeight[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin || !userId) return;
    Promise.all([getAdminOverview(userId), getAdminUsers(userId), getAdminSignals(userId)])
      .then(([o, u, s]) => {
        setOverview(o);
        setUsers(u.users);
        setSignals(s.signals);
      })
      .catch((e) => setError(String(e)));
    getLearningStats().then((r) => setLearning(r.strategies)).catch(() => {});
  }, [isAdmin, userId]);

  if (status === "loading") return <p className="text-sm text-neutral-500">Loading…</p>;

  // Don't reveal this is an admin console to non-admins — show a generic 404-style message.
  if (!session?.user || !isAdmin) {
    return (
      <div className="max-w-md mx-auto mt-12 text-center">
        <h1 className="text-lg font-semibold text-neutral-100">Page not found</h1>
        <p className="mt-2 text-sm text-neutral-500">
          The page you’re looking for doesn’t exist.
        </p>
        <Link href="/" className="mt-4 inline-block text-sm text-cyan-400 underline underline-offset-2">
          Go home
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-lg font-semibold text-neutral-100">Admin overview</h1>
      {error && <p className="text-rose-400 text-sm">{error}</p>}

      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Users", value: overview.user_count },
            { label: "Signals today", value: overview.signals_today },
            { label: "Signals total", value: overview.signals_total },
            { label: "Data source", value: overview.data_source },
          ].map((stat) => (
            <div key={stat.label} className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <p className="text-xs text-neutral-500">{stat.label}</p>
              <p className="text-xl font-semibold text-neutral-100 font-mono">{stat.value}</p>
            </div>
          ))}
        </div>
      )}

      {overview && (
        <section>
          <h2 className="text-sm font-medium text-neutral-300 mb-2">Candle cache per symbol</h2>
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
            {overview.tracked_symbols.map((sym) => {
              const cache = overview.candle_cache[sym];
              const lastSignal = overview.last_signal_by_symbol[sym];
              return (
                <div key={sym} className="flex items-center justify-between px-4 py-2 text-sm">
                  <span className="font-mono text-neutral-200">{sym}</span>
                  <span className="text-neutral-500 text-xs">
                    {cache ? `${cache.candle_count} candles · last ${cache.last_ts}` : "no data yet"}
                    {lastSignal ? ` · last signal ${lastSignal}` : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-medium text-neutral-300 mb-2">Strategy learning (adaptive weights)</h2>
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
          {learning.length === 0 ? (
            <p className="px-4 py-3 text-sm text-neutral-500">
              No graded trades yet — weights stay neutral (1.0) until the bot&apos;s paper trades close.
            </p>
          ) : (
            learning.map((s) => (
              <div key={s.name} className="flex items-center justify-between px-4 py-2 text-sm">
                <span className="text-neutral-200">{s.name}</span>
                <span className="text-xs text-neutral-500">
                  {s.wins}/{s.total} wins ·{" "}
                  <span className={s.weight > 1 ? "text-emerald-400" : s.weight < 1 ? "text-rose-400" : "text-neutral-400"}>
                    weight {s.weight}
                  </span>
                </span>
              </div>
            ))
          )}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-300 mb-2">Users</h2>
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-4 py-2 text-sm">
              <span className="text-neutral-200">{u.email}</span>
              <span className="text-xs text-neutral-500">
                {u.is_admin ? "admin" : "user"} · joined {u.created_at}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-300 mb-2">All signals ({signals.length})</h2>
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
          {signals.map((s) => (
            <div key={s.id} className="flex items-center justify-between px-4 py-2 text-sm">
              <span className="font-mono text-neutral-200">
                {s.symbol} · {s.date}
              </span>
              <span className="text-xs text-neutral-500">
                {s.direction} · confluence {s.confluence_score} · hit-rate{" "}
                {s.backtest_hit_rate != null ? `${(s.backtest_hit_rate * 100).toFixed(1)}%` : "n/a"}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
