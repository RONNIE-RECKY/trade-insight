"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { cancelScheduledChange, getApiKey, getPlanStatus, getPlans, hasApiAccess, type Plan, type PlanStatus } from "@/lib/api";
import { Pricing } from "@/components/Pricing";

export default function AccountPage() {
  const { data: session, status } = useSession();
  const plan = (session?.user as { plan?: string } | undefined)?.plan ?? "free";
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;
  const [plans, setPlans] = useState<Plan[]>([]);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [apiBusy, setApiBusy] = useState(false);
  const [planStatus, setPlanStatus] = useState<PlanStatus | null>(null);
  const [cancelBusy, setCancelBusy] = useState(false);

  useEffect(() => {
    getPlans().then((res) => setPlans(res.plans)).catch(() => {});
  }, []);

  const refreshPlanStatus = () => {
    if (userId) getPlanStatus(userId).then(setPlanStatus).catch(() => {});
  };

  useEffect(() => {
    refreshPlanStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function undoScheduledChange() {
    if (!userId) return;
    setCancelBusy(true);
    try {
      await cancelScheduledChange(userId);
      refreshPlanStatus();
    } finally {
      setCancelBusy(false);
    }
  }

  async function revealApiKey() {
    if (!userId) return;
    setApiBusy(true);
    try {
      const res = await getApiKey(userId);
      setApiKey(res.api_key);
    } catch {
      /* not entitled */
    } finally {
      setApiBusy(false);
    }
  }

  if (status === "loading") return <p className="text-sm text-neutral-500">Loading…</p>;

  if (!session?.user) {
    return (
      <p className="text-sm text-neutral-400">
        <Link href="/login" className="text-cyan-400 underline underline-offset-2">
          Log in
        </Link>{" "}
        to view your account and package.
      </p>
    );
  }

  const current = plans.find((p) => p.id === plan);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-neutral-100">Account</h1>
        <p className="text-sm text-neutral-500">{session.user.email}</p>
      </div>

      <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-b from-cyan-500/10 to-neutral-900/60 p-6">
        <p className="text-xs uppercase tracking-wide text-cyan-300">Your package</p>
        <p className="mt-1 text-2xl font-bold text-neutral-50 capitalize">{current?.name ?? plan}</p>
        {current && (
          <>
            <p className="text-sm text-neutral-400">
              {current.price === 0 ? "Free plan" : `$${current.price}/mo`} · {current.tagline}
            </p>
            <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-neutral-300">
              {current.features.map((f) => (
                <li key={f} className="flex gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </>
        )}
        {planStatus?.pending_plan && (
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
            <p>
              Scheduled change: your plan will switch to{" "}
              <span className="font-semibold capitalize">{planStatus.pending_plan}</span>
              {planStatus.plan_period_end ? ` on ${planStatus.plan_period_end.slice(0, 10)}` : ""}. You keep
              your current features until then.
            </p>
            <button
              onClick={undoScheduledChange}
              disabled={cancelBusy}
              className="mt-2 rounded-md border border-amber-400/40 px-3 py-1 text-amber-100 hover:bg-amber-500/10 disabled:opacity-50"
            >
              {cancelBusy ? "Working…" : "Keep current plan instead"}
            </button>
          </div>
        )}
      </div>

      {hasApiAccess(plan) && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6">
          <p className="text-xs uppercase tracking-wide text-emerald-300">Platinum · API access</p>
          <p className="mt-1 text-sm text-neutral-400">
            Pull today&apos;s signals programmatically. Keep this key secret.
          </p>
          {apiKey ? (
            <div className="mt-3 space-y-2">
              <code className="block break-all rounded-lg border border-neutral-800 bg-neutral-950/60 px-3 py-2 text-xs text-emerald-300">
                {apiKey}
              </code>
              <p className="text-xs text-neutral-500 font-mono break-all">
                GET /api/v1/signals?api_key={apiKey.slice(0, 10)}…
              </p>
            </div>
          ) : (
            <button
              onClick={revealApiKey}
              disabled={apiBusy}
              className="mt-3 rounded-lg border border-emerald-500/40 px-4 py-2 text-sm font-medium text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50"
            >
              {apiBusy ? "Loading…" : "Reveal API key"}
            </button>
          )}
        </div>
      )}

      <div>
        <h2 className="text-lg font-semibold text-neutral-100 mb-1">Change package</h2>
        <p className="text-sm text-neutral-500 mb-5">
          Upgrade anytime — it applies immediately. Downgrading or cancelling takes effect at the end of your
          current billing period, so you keep your current features until then.
        </p>
        <Pricing onChanged={refreshPlanStatus} />
      </div>
    </div>
  );
}
