"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { checkout, getPlans, PLAN_RANK, scheduleChange, type Plan } from "@/lib/api";

export function Pricing({ onChanged }: { onChanged?: () => void } = {}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [paymentsEnabled, setPaymentsEnabled] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const currentPlan = (session?.user as { plan?: string } | undefined)?.plan ?? null;
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;

  useEffect(() => {
    getPlans()
      .then((res) => {
        setPlans(res.plans);
        setPaymentsEnabled(res.payments_enabled);
      })
      .catch((e) => setError(String(e)));
  }, []);

  async function choose(planId: string) {
    setError(null);
    setInfo(null);
    if (!userId) {
      // must have an account first
      router.push(planId === "free" ? "/signup" : `/signup?plan=${planId}`);
      return;
    }

    const currentRank = PLAN_RANK[currentPlan ?? "free"] ?? 0;
    const targetRank = PLAN_RANK[planId] ?? 0;

    if (targetRank > currentRank) {
      // upgrade — takes effect immediately, only after real payment
      if (!paymentsEnabled) return; // button is disabled in this state
      setBusy(planId);
      try {
        const { url } = await checkout(userId, planId);
        window.location.href = url;
      } catch (e) {
        setError(String(e).replace("Error:", "").trim());
      } finally {
        setBusy(null);
      }
      return;
    }

    // downgrade (or cancel to free) — scheduled for the end of the current period
    setBusy(planId);
    try {
      const res = await scheduleChange(userId, planId);
      if (res.effective === "immediately") {
        setInfo(`Switched to ${planId === "free" ? "Free" : planId} immediately.`);
      } else {
        setInfo(
          `Your plan will change to ${plans.find((p) => p.id === planId)?.name ?? planId} at the end of your ` +
            `current billing period${res.effective ? ` (${res.effective.slice(0, 10)})` : ""}. You keep your ` +
            `current features until then.`
        );
      }
      onChanged?.();
    } catch (e) {
      setError(String(e).replace("Error:", "").trim());
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      {error && <p className="text-rose-400 text-sm mb-3">{error}</p>}
      {info && <p className="text-emerald-400 text-sm mb-3">{info}</p>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => {
          const isCurrent = currentPlan === plan.id;
          const currentRank = PLAN_RANK[currentPlan ?? "free"] ?? 0;
          const targetRank = PLAN_RANK[plan.id] ?? 0;
          const isDowngrade = !isCurrent && userId != null && targetRank < currentRank;
          return (
            <div
              key={plan.id}
              className={`relative flex flex-col rounded-2xl border p-6 ${
                plan.popular
                  ? "border-cyan-500/50 bg-gradient-to-b from-cyan-500/10 to-neutral-900/60"
                  : "border-neutral-800 bg-neutral-900/40"
              }`}
            >
              {plan.popular && (
                <span className="absolute -top-3 left-6 rounded-full bg-gradient-to-br from-cyan-500 to-emerald-500 px-3 py-0.5 text-[11px] font-semibold text-neutral-950">
                  {plan.tagline}
                </span>
              )}
              <h3 className="text-lg font-semibold text-neutral-100">{plan.name}</h3>
              {!plan.popular && <p className="text-xs text-neutral-500">{plan.tagline}</p>}
              <p className="mt-3">
                <span className="text-3xl font-bold text-neutral-50">
                  {plan.price === 0 ? "Free" : `$${plan.price}`}
                </span>
                {plan.price > 0 && <span className="text-sm text-neutral-500">/mo</span>}
              </p>
              {plan.highlight && (
                <p className="mt-2 inline-block rounded-md bg-cyan-500/10 px-2 py-0.5 text-xs font-medium text-cyan-300">
                  {plan.highlight}
                </p>
              )}
              <ul className="mt-4 space-y-2 text-sm text-neutral-300 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-emerald-400">✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              {(() => {
                const paidLocked = plan.price > 0 && !paymentsEnabled && !isDowngrade;
                return (
                  <button
                    onClick={() => choose(plan.id)}
                    disabled={isCurrent || busy === plan.id || paidLocked}
                    className={`mt-6 rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-60 ${
                      plan.popular
                        ? "bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950"
                        : "border border-neutral-700 text-neutral-100 hover:border-neutral-500"
                    }`}
                  >
                    {isCurrent
                      ? "Current plan"
                      : busy === plan.id
                      ? "Working…"
                      : isDowngrade
                      ? plan.id === "free"
                        ? "Cancel to Free"
                        : "Downgrade"
                      : paidLocked
                      ? "Coming soon"
                      : plan.price === 0
                      ? "Get started"
                      : "Upgrade"}
                  </button>
                );
              })()}
            </div>
          );
        })}
      </div>
      <p className="mt-4 text-center text-xs text-neutral-600">
        {paymentsEnabled
          ? "Secure checkout. Your plan activates only after payment is confirmed."
          : "Paid plans are launching soon. Start free today."}
      </p>
    </div>
  );
}
