"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getPlans, type Plan } from "@/lib/api";

export default function ChoosePlanPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [choosing, setChoosing] = useState<string | null>(null);

  useEffect(() => {
    getPlans()
      .then((res) => setPlans(res.plans))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function pick(planId: string) {
    setChoosing(planId);
    if (planId === "free") {
      localStorage.removeItem("pendingPlan");
    } else {
      localStorage.setItem("pendingPlan", planId);
    }
    router.push("/login");
  }

  if (loading) {
    return <p className="text-sm text-neutral-500 text-center mt-20">Loading plans…</p>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-8">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold text-neutral-100">Choose your package</h1>
        <p className="text-sm text-neutral-400">
          Your account is verified. Pick a plan — you can upgrade or cancel anytime.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => (
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
            <button
              onClick={() => pick(plan.id)}
              disabled={choosing !== null}
              className={`mt-6 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:opacity-60 transition-opacity ${
                plan.popular
                  ? "bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950"
                  : "border border-neutral-700 text-neutral-100 hover:border-neutral-500"
              }`}
            >
              {choosing === plan.id
                ? "One moment…"
                : plan.price === 0
                ? "Start free"
                : "Choose plan"}
            </button>
          </div>
        ))}
      </div>

    </div>
  );
}
