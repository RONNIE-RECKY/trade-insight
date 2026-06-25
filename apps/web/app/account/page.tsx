"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { getPlans, subscribe, type Plan } from "@/lib/api";
import { Pricing } from "@/components/Pricing";

export default function AccountPage() {
  const { data: session, status, update } = useSession();
  const plan = (session?.user as { plan?: string } | undefined)?.plan ?? "free";
  const userId = session?.user ? Number((session.user as { id?: string }).id) : null;
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    getPlans().then((res) => setPlans(res.plans)).catch(() => {});
  }, []);

  // Apply a plan chosen on the pricing page before the account existed.
  useEffect(() => {
    if (!userId) return;
    const pending = typeof window !== "undefined" ? localStorage.getItem("pendingPlan") : null;
    if (pending && pending !== "free" && pending !== plan) {
      subscribe(userId, pending)
        .then(() => update({ plan: pending }))
        .catch(() => {})
        .finally(() => localStorage.removeItem("pendingPlan"));
    } else if (pending) {
      localStorage.removeItem("pendingPlan");
    }
  }, [userId, plan, update]);

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
      </div>

      <div>
        <h2 className="text-lg font-semibold text-neutral-100 mb-1">Change package</h2>
        <p className="text-sm text-neutral-500 mb-5">Upgrade or switch your plan at any time.</p>
        <Pricing />
      </div>
    </div>
  );
}
