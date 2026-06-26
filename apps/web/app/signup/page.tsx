"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { resendCode, signup, verifyCode } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // verification step
  const [stage, setStage] = useState<"form" | "code">("form");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [emailAttempted, setEmailAttempted] = useState(false);
  const [verifying, setVerifying] = useState(false);

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await signup(email, password);
      const plan = new URLSearchParams(window.location.search).get("plan");
      if (plan) localStorage.setItem("pendingPlan", plan);
      setDevCode(res.verification_code ?? null);
      setEmailAttempted(Boolean(res.email_sent));
      setStage("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setVerifying(true);
    setError(null);
    try {
      await verifyCode(email, code.trim());
      router.push("/login");
    } catch {
      setError("That code is incorrect. Check the 6-digit code we emailed you.");
    } finally {
      setVerifying(false);
    }
  }

  async function handleResend() {
    setError(null);
    try {
      const res = await resendCode(email);
      setDevCode(res.verification_code ?? null);
      setEmailAttempted(Boolean(res.email_sent));
    } catch {
      setError("Couldn't resend the code.");
    }
  }

  if (stage === "code") {
    return (
      <div className="max-w-sm mx-auto bg-neutral-900/60 border border-neutral-800 rounded-xl p-6 space-y-4">
        <h1 className="text-lg font-semibold text-neutral-100">Enter your code</h1>
        <p className="text-sm text-neutral-400">
          {emailAttempted
            ? <>We sent a 6-digit verification code to <span className="text-neutral-200">{email}</span>. Enter it below to activate your account.</>
            : <>Enter the 6-digit code below to activate your account.</>}
        </p>
        {devCode && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
            {emailAttempted
              ? "Email may take a minute to arrive (check spam) — or use this code now:"
              : "Your verification code:"}{" "}
            <span className="font-mono text-base tracking-widest text-amber-100">{devCode}</span>
          </div>
        )}
        <form onSubmit={handleVerify} className="space-y-3">
          <input
            inputMode="numeric"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            placeholder="123456"
            className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-center text-lg font-mono tracking-[0.5em] text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
          {error && <p className="text-rose-400 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={verifying || code.length < 6}
            className="w-full bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950 rounded-md px-3 py-2 text-sm font-semibold disabled:opacity-50"
          >
            {verifying ? "Verifying…" : "Verify & continue"}
          </button>
        </form>
        <button onClick={handleResend} className="text-xs text-cyan-400 underline underline-offset-2">
          Resend code
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-sm mx-auto bg-neutral-900/60 border border-neutral-800 rounded-xl p-6 space-y-4">
      <h1 className="text-lg font-semibold text-neutral-100">Sign up</h1>
      <form onSubmit={handleSignup} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-neutral-400">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-1.5 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-400">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            className="mt-1 w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-1.5 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
        </div>
        {error && <p className="text-rose-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Sign up"}
        </button>
      </form>
      <p className="text-xs text-neutral-500">
        Already have an account?{" "}
        <Link href="/login" className="text-cyan-400 underline underline-offset-2">
          Log in
        </Link>
      </p>
    </div>
  );
}
