"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { RequireAuth } from "@/components/RequireAuth";
import {
  canAutoTrade,
  confirmMT5Trade,
  connectBroker,
  connectMT5,
  connectMT5Live,
  disconnectMT5,
  getAutoTradePositions,
  getAutoTradeSettings,
  getBroker,
  getPendingMT5Trades,
  updateAutoTradeSettings,
  type AutoTrade,
  type AutoTradePositions,
  type AutoTradeSettings,
  type BrokerConnection,
  type PendingTrade,
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
  const [venue, setVenue] = useState<"simulated" | "oanda" | "mt5" | "mt5-live">("simulated");
  const [acctId, setAcctId] = useState("");
  const [token, setToken] = useState("");
  const [riskAck, setRiskAck] = useState(false);
  const [brokerMsg, setBrokerMsg] = useState<string | null>(null);
  const [mt5ApiKey, setMt5ApiKey] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingTrade[]>([]);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

  const refreshPending = useCallback(() => {
    if (!userId) return;
    getPendingMT5Trades(userId)
      .then((r) => setPending(r.pending))
      .catch(() => {});
  }, [userId]);

  const load = useCallback(() => {
    if (!userId || !entitled) return;
    Promise.all([getAutoTradeSettings(userId), getAutoTradePositions(userId), getBroker(userId)])
      .then(([s, p, b]) => {
        setSettings(s);
        setPositions(p);
        setBroker(b);
        setVenue(b.provider === "oanda" ? "oanda" : b.provider === "mt5" ? (b.mode === "live" ? "mt5-live" : "mt5") : "simulated");
        if (b.provider === "mt5" && b.mode === "live") refreshPending();
      })
      .catch((e) => setError(String(e)));
  }, [userId, entitled, refreshPending]);

  async function saveBroker() {
    if (!userId) return;
    setBrokerMsg(null);
    try {
      if (venue === "mt5") {
        const res = await connectMT5(userId, acctId || undefined);
        setMt5ApiKey(res.api_key);
        setBrokerMsg("MT5 demo bridge connected. Paste the API key below into your EA's inputs.");
        const b = await getBroker(userId);
        setBroker(b);
        return;
      }
      if (venue === "mt5-live") {
        if (!riskAck) {
          setBrokerMsg("You must acknowledge the risk of live trading to connect a live account.");
          return;
        }
        const res = await connectMT5Live(userId, acctId || undefined, riskAck);
        setMt5ApiKey(res.api_key);
        setBrokerMsg(
          "MT5 LIVE bridge connected. Paste the API key below into your EA's inputs. Every signal will need " +
            "your confirmation (in-app or via email link) before it executes — nothing fires automatically."
        );
        const b = await getBroker(userId);
        setBroker(b);
        return;
      }
      const body =
        venue === "simulated" ? { provider: "simulated" } : { provider: "oanda", account_id: acctId, token };
      const b = await connectBroker(userId, body);
      setBroker(b);
      setBrokerMsg(
        venue === "oanda"
          ? "Demo account connected. The bot will place real orders on your practice account."
          : "Using the internal simulator."
      );
    } catch (e) {
      setBrokerMsg(String(e).replace("Error:", "").trim());
    }
  }

  async function confirmTrade(id: number) {
    if (!userId) return;
    setConfirmingId(id);
    try {
      await confirmMT5Trade(userId, id);
      refreshPending();
    } catch (e) {
      setBrokerMsg(String(e).replace("Error:", "").trim());
    } finally {
      setConfirmingId(null);
    }
  }

  async function disconnectMT5Bridge() {
    if (!userId) return;
    await disconnectMT5(userId);
    setMt5ApiKey(null);
    setBrokerMsg("MT5 bridge disconnected.");
    const b = await getBroker(userId);
    setBroker(b);
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
          The bot auto-opens positions from your signals. By default it uses an internal paper simulator —{" "}
          <span className="text-neutral-300">no real money or broker orders</span>. You can optionally connect a
          DEMO broker account (OANDA practice, or MT5 via the EA bridge) for authentic automated execution on
          practice funds.
        </p>
      </div>

      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
        Results don’t guarantee future performance. This platform only ever connects DEMO / practice broker
        accounts for automated execution — it does not support connecting a live, real-money account here.
      </div>

      {error && <p className="text-rose-400 text-sm">{error}</p>}

      {/* Trading account / broker connection — DEMO accounts only */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5 space-y-4">
        <div>
          <h2 className="font-medium text-neutral-100">Trading account</h2>
          <p className="text-xs text-neutral-500">
            This platform only connects DEMO / practice accounts for automated execution — never a live,
            real-money account. Currently:{" "}
            <span className="text-neutral-300">
              {broker?.provider === "simulated" || !broker?.connected
                ? "internal simulator"
                : `${broker.provider} demo`}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {(["simulated", "oanda", "mt5", "mt5-live"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setVenue(v)}
              className={`text-xs font-medium px-3 py-1.5 rounded-md border ${
                venue === v
                  ? v === "mt5-live"
                    ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
                    : "border-cyan-500/50 bg-cyan-500/10 text-cyan-300"
                  : "border-neutral-700 text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {v === "simulated"
                ? "Internal simulator"
                : v === "oanda"
                ? "OANDA demo"
                : v === "mt5"
                ? "MT5 demo (EA bridge)"
                : "MT5 LIVE (confirm each trade)"}
            </button>
          ))}
        </div>

        {venue === "oanda" && (
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
              placeholder="Practice API token"
              className="bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-100"
            />
          </div>
        )}

        {venue === "mt5" && (
          <div className="space-y-3">
            <p className="text-xs text-neutral-400">
              Connect to get an API key for the PIP HIVE MT5 Expert Advisor. Install the EA on your MT5{" "}
              <span className="text-neutral-200">demo</span> terminal, paste the key into its inputs, and it
              will poll for and execute queued orders automatically.
            </p>
            <input
              value={acctId}
              onChange={(e) => setAcctId(e.target.value)}
              placeholder="Your MT5 demo login number (optional, for your reference)"
              className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-100"
            />
            {mt5ApiKey && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
                <p className="text-xs text-emerald-300 mb-1">
                  Your EA API key (shown once — copy it now):
                </p>
                <code className="block break-all text-xs text-emerald-200 font-mono">{mt5ApiKey}</code>
              </div>
            )}
            {broker?.provider === "mt5" && broker.connected && (
              <button
                onClick={disconnectMT5Bridge}
                className="text-xs text-rose-300 underline underline-offset-2"
              >
                Disconnect MT5 bridge
              </button>
            )}
          </div>
        )}

        {venue === "mt5-live" && (
          <div className="space-y-3">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
              This connects a real, live MT5 account with real money. The bot will still propose trades from
              your signals, but it will <span className="font-semibold">never execute one automatically</span> —
              you must confirm each trade yourself, either with the button below or the link sent to your email,
              before it goes to your EA. Unconfirmed trades expire after 15 minutes and are never sent.
            </div>
            <input
              value={acctId}
              onChange={(e) => setAcctId(e.target.value)}
              placeholder="Your MT5 live login number (optional, for your reference)"
              className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-100"
            />
            <label className="flex items-start gap-2 text-xs text-neutral-300">
              <input
                type="checkbox"
                checked={riskAck}
                onChange={(e) => setRiskAck(e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-amber-500"
              />
              I understand this connects a live account and trades will use real money once I confirm them.
            </label>
            {mt5ApiKey && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
                <p className="text-xs text-emerald-300 mb-1">Your EA API key (shown once — copy it now):</p>
                <code className="block break-all text-xs text-emerald-200 font-mono">{mt5ApiKey}</code>
              </div>
            )}
            {broker?.provider === "mt5" && broker.mode === "live" && broker.connected && (
              <button onClick={disconnectMT5Bridge} className="text-xs text-rose-300 underline underline-offset-2">
                Disconnect MT5 live bridge
              </button>
            )}
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={saveBroker}
            className="rounded-md bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950 disabled:opacity-50"
          >
            {venue === "simulated"
              ? "Use simulator"
              : venue === "mt5" || venue === "mt5-live"
              ? "Generate API key"
              : "Connect account"}
          </button>
          {brokerMsg && <span className="text-xs text-neutral-400">{brokerMsg}</span>}
        </div>
      </div>

      {/* Pending live-trade confirmations */}
      {broker?.provider === "mt5" && broker.mode === "live" && pending.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-3">
          <h2 className="font-medium text-amber-200">Trades awaiting your confirmation</h2>
          {pending.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-neutral-200">{t.symbol}</span>
                <span className={dirClass(t.direction)}>{t.direction}</span>
                <span className="text-xs text-neutral-500 font-mono">
                  @ {t.entry} · SL {t.stop_loss} · TP {t.take_profit}
                </span>
              </div>
              <button
                disabled={confirmingId === t.id}
                onClick={() => confirmTrade(t.id)}
                className="rounded-md bg-gradient-to-br from-amber-500 to-orange-500 px-3 py-1.5 text-xs font-semibold text-neutral-950 disabled:opacity-50"
              >
                {confirmingId === t.id ? "Confirming…" : "Confirm & Execute"}
              </button>
            </div>
          ))}
        </div>
      )}

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
            {broker?.provider === "mt5" && broker.connected && (
              <label className="flex items-center justify-between bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2 text-sm">
                <span className="text-neutral-300">MT5 lot size</span>
                <input
                  type="number"
                  min={0.01}
                  max={100}
                  step={0.01}
                  value={settings.mt5_lot_size}
                  onChange={(e) => setSettings({ ...settings, mt5_lot_size: Number(e.target.value) })}
                  onBlur={() => save(settings)}
                  className="w-20 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-right text-neutral-100"
                />
              </label>
            )}
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
