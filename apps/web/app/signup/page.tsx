"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { resendCode, signup, verifyCode } from "@/lib/api";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

function SignupForm() {
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [stage, setStage] = useState<"form" | "code">("form");
  const [code, setCode] = useState("");
  const [verifying, setVerifying] = useState(false);

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    if (!termsAccepted) {
      setError("You must accept the Terms of Service and Privacy Policy to continue.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await signup(email, password, fullName, phone, termsAccepted);
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
      router.push("/choose-plan");
    } catch {
      setError("That code is incorrect. Check the 6-digit code we emailed you.");
    } finally {
      setVerifying(false);
    }
  }

  async function handleResend() {
    setError(null);
    try {
      await resendCode(email);
    } catch {
      setError("Couldn't resend the code — please try again.");
    }
  }

  if (stage === "code") {
    return (
      <div className="max-w-sm mx-auto bg-neutral-900/60 border border-neutral-800 rounded-xl p-6 space-y-4">
        <h1 className="text-lg font-semibold text-neutral-100">Check your email</h1>
        <p className="text-sm text-neutral-400">
          We sent a 6-digit verification code to{" "}
          <span className="text-neutral-200">{email}</span>. Enter it below to activate your account.
        </p>
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
    <div className="max-w-md mx-auto bg-neutral-900/60 border border-neutral-800 rounded-xl p-6 space-y-4">
      <h1 className="text-lg font-semibold text-neutral-100">Sign up</h1>
      <form onSubmit={handleSignup} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-neutral-400">Full name</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            placeholder="First Last"
            className="mt-1 w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-1.5 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-400">Phone number</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
            placeholder="+254 700 000000"
            className="mt-1 w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-1.5 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
        </div>
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
            minLength={8}
            className="mt-1 w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-1.5 text-sm text-neutral-100 focus:outline-none focus:ring-1 focus:ring-cyan-500"
          />
          <p className="mt-1 text-xs text-neutral-500">
            8+ characters, uppercase, lowercase, number and symbol. Cannot contain your name or email.
          </p>
        </div>

        <label className="flex items-start gap-2 text-xs text-neutral-400">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-emerald-500"
          />
          <span>
            I agree to the{" "}
            <Link href="/terms" target="_blank" className="text-emerald-400 underline underline-offset-2">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="/privacy" target="_blank" className="text-emerald-400 underline underline-offset-2">
              Privacy Policy
            </Link>
            .
          </span>
        </label>

        {error && <p className="text-rose-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={submitting || !termsAccepted}
          className="w-full bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Sign up"}
        </button>
      </form>
      <GoogleSignInButton />
      <p className="text-xs text-neutral-500">
        Already have an account?{" "}
        <Link href="/login" className="text-cyan-400 underline underline-offset-2">
          Log in
        </Link>
      </p>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<p className="text-sm text-neutral-500">Loading…</p>}>
      <SignupForm />
    </Suspense>
  );
}
