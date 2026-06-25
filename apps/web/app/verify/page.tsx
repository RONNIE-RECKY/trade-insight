"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { resendCode, verifyCode } from "@/lib/api";

export default function VerifyPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await verifyCode(email, code.trim());
      router.push("/login");
    } catch {
      setError("That code is incorrect or expired.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResend() {
    setError(null);
    setInfo(null);
    try {
      const res = await resendCode(email);
      setInfo(res.verification_code ? `Demo code: ${res.verification_code}` : "A new code has been sent.");
    } catch {
      setError("Couldn't resend — is the email correct?");
    }
  }

  return (
    <div className="max-w-sm mx-auto bg-neutral-900/60 border border-neutral-800 rounded-xl p-6 space-y-4">
      <h1 className="text-lg font-semibold text-neutral-100">Verify your email</h1>
      <p className="text-sm text-neutral-400">Enter the 6-digit code we emailed you.</p>
      <form onSubmit={handleVerify} className="space-y-3">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
        />
        <input
          inputMode="numeric"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          placeholder="123456"
          className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-center text-lg font-mono tracking-[0.5em] text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
        />
        {error && <p className="text-rose-400 text-sm">{error}</p>}
        {info && <p className="text-amber-300 text-sm">{info}</p>}
        <button
          type="submit"
          disabled={busy || code.length < 6}
          className="w-full bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950 rounded-md px-3 py-2 text-sm font-semibold disabled:opacity-50"
        >
          {busy ? "Verifying…" : "Verify"}
        </button>
      </form>
      <div className="flex justify-between text-xs">
        <button onClick={handleResend} className="text-cyan-400 underline underline-offset-2">
          Resend code
        </button>
        <Link href="/login" className="text-neutral-400 underline underline-offset-2">
          Back to login
        </Link>
      </div>
    </div>
  );
}
