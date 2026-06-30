"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { confirmMT5TradeByToken } from "@/lib/api";

function ConfirmTradeInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"checking" | "confirmed" | "failed">("checking");

  useEffect(() => {
    if (!token) {
      setStatus("failed");
      return;
    }
    confirmMT5TradeByToken(token)
      .then((ok) => setStatus(ok ? "confirmed" : "failed"))
      .catch(() => setStatus("failed"));
  }, [token]);

  return (
    <div className="max-w-md mx-auto mt-12 rounded-2xl border border-neutral-800 bg-neutral-900/60 p-8 text-center">
      {status === "checking" && <p className="text-sm text-neutral-400">Confirming your trade…</p>}
      {status === "confirmed" && (
        <>
          <h1 className="text-lg font-semibold text-emerald-400">Trade confirmed</h1>
          <p className="mt-2 text-sm text-neutral-400">
            It will execute on your live MT5 terminal the next time your EA polls (usually within a few seconds).
          </p>
        </>
      )}
      {status === "failed" && (
        <>
          <h1 className="text-lg font-semibold text-rose-400">This link is no longer valid</h1>
          <p className="mt-2 text-sm text-neutral-400">
            It may have already been used, or the confirmation window expired. Check the auto-trade page for
            other pending trades.
          </p>
        </>
      )}
      <Link href="/auto-trade" className="mt-5 inline-block text-xs text-cyan-300 underline underline-offset-2">
        Go to auto-trade dashboard
      </Link>
    </div>
  );
}

export default function ConfirmTradePage() {
  return (
    <Suspense fallback={null}>
      <ConfirmTradeInner />
    </Suspense>
  );
}
