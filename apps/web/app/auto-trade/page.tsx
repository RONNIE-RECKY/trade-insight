"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { RequireAuth } from "@/components/RequireAuth";
import {
  canAutoTrade,
  connectBroker,
  getAutoTradePositions,
  getAutoTradeSettings,
  getBroker,
  updateAutoTradeSettings,
  type AutoTrade,
  type AutoTradePositions,
  type AutoTradeSettings,
  type BrokerConnection,
} from "@/lib/api";

function dirClass(d: string) {
  if (d === "bullish") return "text-emerald-400";
  if (d === "bearish") return "text-rose-400";
  return "text-neutral-400";
}

function TradeRow({ t }: { t: AutoTrade }) {
  const pnl = t.pnl_pct;
  return (
    <div className="flex items-center justify-between px-4 py-2 text-sm border-b border-neutral-800 last:border-0">
      <div className="flex items-center gap-2">
        <span className="font-mono text-neutral-200">{t.symbol}</span>
        {t.interval && <span className="text-[10px] text-neutral-500 bg-neutral-800 rounded px-1.5 py-0.5">{t.interval}</span>}
        <span className={`text-xs ${dirClass(t.direction)}`}>{t.direction}</span>
        {t.venue && t.venue !== "simulated" && (
          <span className="text-[10px] text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 rounded px-1.5 py-0.5">
            {t.venue}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 font-mono text-xs">
        <span className="text-neutral-500">@ {t.entry}</span>
        {t.status === "open" ? (
          <span className="text-amber-300">open</span>
        ) : (
          <span className={t.outcome === "win" ? "text-emerald-400" : "text-rose-400"}>
            {t.outcome} {pnl != null ? `${pnl > 0 ? "+" : ""}${pnl}%` : ""}
          </span>
        )}
      </div>
    </div>
  );
}

function AutoTradeInner() {
  const { data: session } = useSession();
  const plan = (session?.user as { plan?: string } | undefined)?.plan;
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;
  const entitled = canAutoTrade(plan);

  const [settings, setSettings] = useState<AutoTradeSettings | null>(null);
  const [positions, setPositions] = useState<AutoTradePositions | null>(null);
  const [broker, setBroker] = useState<BrokerConnection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // broker form state
  const [venue, setVenue] = useState<"simulated" | "demo" | "live">("simulated");
  const [acctId, setAcctId] = useState("");
  const [token, setToken] = useState("");
  const [ack, setAck] = useState(false);
  const [brokerMsg, setBrokerMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!userId || !entitled) return;
    Promise.all([getAutoTradeSettings(userId), getAutoTradePositions(userId), getBroker(userId)])
      .then(([s, p, b]) => {
        setSettings(s);
        setPositions(p);
        setBroker(b);
        setVenue(b.provider === "simulated" ? "simulated" : b.mode === "live" ? "live" : "demo");
      })
      .catch((e) => setError(String(e)));
  }, [userId, entitled]);

  async function saveBroker() {
    if (!userId) return;
    setBrokerMsg(null);
    try {
      const body =
        venue === "simulated"
          ? { provider: "simulated", mode: "demo" }
          : venue === "demo"
          ? { provider: "oanda", mode: "demo", account_id: acctId, token }
          : { provider: "oanda", mode: "live", account_id: acctId, token, risk_acknowledged: ack };
      const b = await connectBroker(userId, body);
      setBroker(b);
      setBrokerMsg(
        venue === "live"
          ? "Live account connected. The bot will NOT auto-place real orders — you confirm each trade yourself."
          : venue === "demo"
          ? "Demo account connected. The bot will place real orders on your practice account."
          : "Using the internal simulator."
      );
    } catch (e) {
      setBrokerMsg(String(e).replace("Error:", "").trim());
    }
  }

  useEffect(() => {
    load();
  }, [load]);

  async function save(next: AutoTradeSettings) {
    if (!userId) return;
    setSaving(true);
    setError(null);
    try {
      const s = await updateAutoTradeSettings(userId, next);
      setSettings(s);
      const p = await getAutoTradePositions(userId);
      setPositions(p);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!entitled) {
    return (
      <div className="max-w-md mx-auto mt-8 rounded-2xl border border-neutral-800 bg-neutral-900/60 p-8 text-center">
        <h1 className="text-lg font-semibold text-neutral-100">Automated trading</h1>
        <p className="mt-2 text-sm text-neutral-400">
          The automated paper-trading bot is part of the <span className="text-cyan-300">Ultimate</span> and{" "}
          <span className="text-emerald-300">Platinum</span> plans.
        </p>
        <Link
          href="/pricing"
          className="mt-5 inline-block rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950"
        >
          Upgrade to unlock
        </Link>
      </div>
    );
  }

  const stats = positions?.stats;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-neutral-100">Automated trading bot</h1>
        <p className="text-xs text-neutral-500 mt-1">
          Simulated (paper) trading. The bot auto-opens positions from your signals and tracks them against
          live prices — <span className="text-neutral-300">no real money or broker orders are involved</span>.
        </p>
      </div>

      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
        This is a hypothetical simulator for education. Results don’t guarantee future performance, and the bot
        never places real trades. Connecting a live brokerage is up to you, with your own account and authorisation.
      </div>

      {error && <p className="text-rose-400 text-sm">{error}</p>}

      {/* Trading account / broker connection */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5 space-y-4">
        <div>
          <h2 className="font-medium text-neutral-100">Trading account</h2>
          <p className="text-xs text-neutral-500">
            Connect a demo account for authentic automated execution, or a live account (with manual
            confirmation). Currently:{" "}
            <span className="text-neutral-300">
              {broker?.provider === "simulated" || !broker?.connected
                ? "internal simulator"
                : `${broker.provider} (${broker.mode})`}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {(["simulated", "demo", "live"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setVenue(v)}
              className={`text-xs font-medium px-3 py-1.5 rounded-md border ${
                venue === v
                  ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-300"
                  : "border-neutral-700 text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {v === "simulated" ? "Internal simulator" : v === "demo" ? "Demo account (real execution)" : "Live account"}
            </button>
          ))}
        </div>

        {venue !== "simulated" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              value={acctId}
              onChange={(e) => setAcctId(e.target.value)}
              placeholder="OANDA account ID (e.g. 101-001-…)"
              className="bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-100"
            />
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              type="password"
              placeholder={venue === "demo" ? "Practice API token" : "Live API token"}
              className="bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-100"
            />
          </div>
        )}

        {venue === "live" && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 space-y-3">
            <p className="text-sm font-semibold text-rose-200">High-risk warning — real money</p>
            <p className="text-xs text-rose-200/90">
              Trading real funds can cause significant losses, up to your entire balance. This software and its
              automated analysis are <span className="font-semibold">not liable</span> for any losses. For live
              accounts the bot does <span className="font-semibold">not</span> place orders automatically — it
              proposes trades and <span className="font-semibold">you confirm each one yourself</span>. Only proceed
              if you fully understand the risks and are authorised to trade.
            </p>
            <label className="flex items-center gap-2 text-xs text-rose-100">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="h-4 w-4 accent-rose-500" />
              I understand the risks and accept that the bot is not liable for any losses.
            </label>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={saveBroker}
            disabled={venue === "live" && !ack}
            className="rounded-md bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950 disabled:opacity-50"
          >
            {venue === "simulated" ? "Use simulator" : "Connect account"}
          </button>
          {brokerMsg && <span className="text-xs text-neutral-400">{brokerMsg}</span>}
        </div>
      </div>

      {/* Controls */}
      {settings && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-neutral-100">Bot status</p>
              <p className="text-xs text-neutral-500">
                {settings.enabled ? "Running — opening simulated positions from signals" : "Stopped"}
              </p>
            </div>
            <button
              disabled={saving}
              onClick={() => save({ ...settings, enabled: !settings.enabled })}
              className={`rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50 ${
                settings.enabled
                  ? "border border-rose-500/40 text-rose-300"
                  : "bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950"
              }`}
            >
              {settings.enabled ? "Stop bot" : "Start bot"}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="flex items-center justify-between bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2 text-sm">
              <span className="text-neutral-300">Max open positions</span>
              <input
                type="number"
                min={1}
                max={50}
                value={settings.max_open}
                onChange={(e) => setSettings({ ...settings, max_open: Number(e.target.value) })}
                onBlur={() => save(settings)}
                className="w-16 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-right text-neutral-100"
              />
            </label>
            <label className="flex items-center justify-between bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2 text-sm">
              <span className="text-neutral-300">Premium signals only</span>
              <input
                type="checkbox"
                checked={settings.only_high_confidence}
                onChange={(e) => save({ ...settings, only_high_confidence: e.target.checked })}
                className="h-4 w-4 accent-cyan-500"
              />
            </label>
          </div>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Open", value: stats.open_count },
            { label: "Closed", value: stats.closed_count },
            { label: "Win rate", value: stats.win_rate != null ? `${stats.win_rate}%` : "—" },
            {
              label: "Total P&L",
              value: `${stats.total_pnl_pct > 0 ? "+" : ""}${stats.total_pnl_pct}%`,
              color: stats.total_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400",
            },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
              <p className="text-xs text-neutral-500">{s.label}</p>
              <p className={`text-xl font-semibold font-mono ${s.color ?? "text-neutral-100"}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section>
          <h2 className="text-sm font-medium text-neutral-300 mb-2">Open positions</h2>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/60">
            {positions && positions.open.length > 0 ? (
              positions.open.map((t) => <TradeRow key={t.id} t={t} />)
            ) : (
              <p className="px-4 py-3 text-sm text-neutral-500">No open positions.</p>
            )}
          </div>
        </section>
        <section>
          <h2 className="text-sm font-medium text-neutral-300 mb-2">Closed positions</h2>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/60">
            {positions && positions.closed.length > 0 ? (
              positions.closed.map((t) => <TradeRow key={t.id} t={t} />)
            ) : (
              <p className="px-4 py-3 text-sm text-neutral-500">No closed positions yet.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export default function AutoTradePage() {
  return (
    <RequireAuth>
      <AutoTradeInner />
    </RequireAuth>
  );
}
