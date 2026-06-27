"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { RequireAuth } from "@/components/RequireAuth";
import { getUploadQuota, uploadChart, type ChartUploadResult, type UploadQuotaStatus } from "@/lib/api";

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

function UploadInner() {
  const { data: session } = useSession();
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;

  const [quota, setQuota] = useState<UploadQuotaStatus | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<ChartUploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshQuota = useCallback(() => {
    if (userId) getUploadQuota(userId).then(setQuota).catch(() => {});
  }, [userId]);

  useEffect(() => {
    refreshQuota();
  }, [refreshQuota]);

  async function handleFile(file: File) {
    if (!userId) return;
    setError(null);
    setResult(null);
    setPreview(URL.createObjectURL(file));
    setBusy(true);
    try {
      const res = await uploadChart(userId, file);
      setResult(res);
      refreshQuota();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const noUploadsAtAll = quota?.quota === 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-neutral-100">Chart upload &amp; analysis</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Upload a chart screenshot — we extract the candles from the image and run the same pattern detection
          and 6-strategy analysis used elsewhere on the platform.
        </p>
      </div>

      {quota && (
        <p className="text-xs text-neutral-500">
          {quota.quota === null
            ? "Unlimited uploads on your plan."
            : quota.quota === 0
            ? "Your plan doesn't include chart uploads."
            : `${quota.remaining} of ${quota.quota} uploads left this period.`}
        </p>
      )}

      {noUploadsAtAll ? (
        <div className="max-w-md rounded-2xl border border-neutral-800 bg-neutral-900/60 p-8 text-center">
          <p className="text-sm text-neutral-400">
            Chart upload &amp; AI pattern detection is available on Pro and above.
          </p>
          <Link
            href="/pricing"
            className="mt-4 inline-block rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950"
          >
            Upgrade to unlock
          </Link>
        </div>
      ) : (
        <>
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files?.[0];
              if (file) handleFile(file);
            }}
            className="cursor-pointer rounded-xl border-2 border-dashed border-neutral-700 bg-neutral-900/40 p-10 text-center hover:border-emerald-500/50 transition-colors"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
            <p className="text-sm text-neutral-300">Click or drag a chart screenshot here</p>
            <p className="mt-1 text-xs text-neutral-500">PNG, JPEG or WEBP, up to 8MB</p>
          </div>

          {preview && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="Uploaded chart" className="max-h-72 w-auto mx-auto rounded-md" />
            </div>
          )}

          {busy && <p className="text-sm text-neutral-500">Analyzing chart…</p>}
          {error && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-300">{error}</div>
          )}

          {result && (
            <>
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
                {result.extraction_note}
              </div>

              <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-semibold text-neutral-100">
                    Detected setup <span className="text-neutral-500 font-normal">({result.candle_count} candles)</span>
                  </h2>
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${directionBadgeClass(result.direction)}`}>
                    {result.direction} · {result.strategy_agreement}
                  </span>
                </div>

                <h3 className="text-sm font-medium text-neutral-300 mb-2">Strategy consensus</h3>
                <ul className="space-y-2">
                  {result.strategies.map((s) => (
                    <li
                      key={s.name}
                      className="flex items-start justify-between gap-3 bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2"
                    >
                      <div>
                        <p className="text-sm font-medium text-neutral-200">{s.name}</p>
                        <p className="text-xs text-neutral-500">{s.reason}</p>
                      </div>
                      <span className={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full ${directionBadgeClass(s.signal)}`}>
                        {s.signal}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {result.current_position && (
                <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
                  <h2 className="font-semibold text-neutral-100 mb-3">Trend &amp; position</h2>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                    <div className="bg-neutral-950/60 border border-neutral-800 rounded-lg p-3">
                      <p className="text-xs text-neutral-500">Trend</p>
                      <p className={`text-sm font-semibold ${trendBadgeClass(result.current_position.trend)}`}>
                        {result.current_position.trend}
                      </p>
                    </div>
                    <div className="bg-neutral-950/60 border border-neutral-800 rounded-lg p-3">
                      <p className="text-xs text-neutral-500">Range position</p>
                      <p className="text-sm font-semibold text-neutral-100">
                        {result.current_position.range_position_pct != null ? `${result.current_position.range_position_pct}%` : "—"}
                      </p>
                    </div>
                    <div className="bg-neutral-950/60 border border-neutral-800 rounded-lg p-3">
                      <p className="text-xs text-neutral-500">vs EMA 20/50</p>
                      <p className="text-sm font-mono">
                        <span className={result.current_position.above_ema_20 ? "text-emerald-400" : "text-rose-400"}>
                          {result.current_position.above_ema_20 ? "above" : "below"}
                        </span>{" "}
                        /{" "}
                        <span className={result.current_position.above_ema_50 ? "text-emerald-400" : "text-rose-400"}>
                          {result.current_position.above_ema_50 ? "above" : "below"}
                        </span>
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {result.levels && result.direction !== "neutral" && (
                <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="font-semibold text-neutral-100">Illustrative trade plan</h2>
                    <span className="text-xs text-neutral-500">{result.price_units}</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: "Entry", value: result.levels.entry, color: "text-sky-400" },
                      { label: "Stop loss", value: result.levels.stop_loss, color: "text-rose-400" },
                      { label: "Take profit", value: result.levels.take_profit, color: "text-emerald-400" },
                      { label: "Risk : Reward", value: `1 : ${result.levels.risk_reward}`, color: "text-neutral-100" },
                    ].map((cell) => (
                      <div key={cell.label} className="bg-neutral-950/60 border border-neutral-800 rounded-lg p-3">
                        <p className="text-xs text-neutral-500">{cell.label}</p>
                        <p className={`text-base font-mono font-semibold ${cell.color}`}>{cell.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-5">
                <h2 className="font-semibold text-neutral-100 mb-3">
                  Chart patterns <span className="text-neutral-500 font-normal">({result.patterns.length})</span>
                </h2>
                {result.patterns.length === 0 ? (
                  <p className="text-sm text-neutral-500">No patterns detected in this image.</p>
                ) : (
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm font-mono">
                    {result.patterns.map((p, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between bg-neutral-950/60 border border-neutral-800 rounded-lg px-3 py-2"
                      >
                        <span className="text-neutral-200">
                          {p.pattern.replace(/_/g, " ")} <span className="text-neutral-500">({p.direction})</span>
                        </span>
                        <span className="text-neutral-400">{p.points.map((pt) => pt.price.toFixed(2)).join(" → ")}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function UploadPage() {
  return (
    <RequireAuth>
      <UploadInner />
    </RequireAuth>
  );
}
