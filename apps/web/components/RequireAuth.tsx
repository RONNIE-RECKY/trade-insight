"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";

/** Gates a feature page behind login. Landing, pricing and auth pages stay public. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useSession();

  if (status === "loading") {
    return <p className="text-sm text-neutral-500">Loading…</p>;
  }

  if (status !== "authenticated") {
    return (
      <div className="max-w-md mx-auto mt-8 rounded-2xl border border-neutral-800 bg-neutral-900/60 p-8 text-center">
        <h1 className="text-lg font-semibold text-neutral-100">Members only</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Log in to use the platform. Your plan decides which features you can access.
        </p>
        <div className="mt-5 flex items-center justify-center gap-3">
          <Link
            href="/login"
            className="rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-4 py-2 text-sm font-semibold text-neutral-950"
          >
            Log in
          </Link>
          <Link
            href="/signup"
            className="rounded-lg border border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-200 hover:border-neutral-500"
          >
            Create account
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
