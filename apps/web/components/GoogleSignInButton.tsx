"use client";

import { useEffect, useState } from "react";
import { getProviders, signIn } from "next-auth/react";

/** Renders only when the backend has Google OAuth configured — keeps the
 * button hidden rather than showing a broken sign-in option. */
export function GoogleSignInButton() {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    getProviders().then((providers) => {
      if (providers && "google" in providers) setAvailable(true);
    });
  }, []);

  if (!available) return null;

  return (
    <>
      <div className="flex items-center gap-3 text-xs text-neutral-500">
        <span className="h-px flex-1 bg-neutral-800" />
        <span>or</span>
        <span className="h-px flex-1 bg-neutral-800" />
      </div>
      <button
        type="button"
        onClick={() => signIn("google", { callbackUrl: "/account" })}
        className="glow-on-hover w-full flex items-center justify-center gap-2 rounded-md border border-neutral-700 px-3 py-2 text-sm font-medium text-neutral-200 hover:border-neutral-500"
      >
        <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden>
          <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84c-.21 1.13-.85 2.09-1.81 2.73v2.27h2.92c1.71-1.58 2.69-3.9 2.69-6.64z" />
          <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.92-2.27c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.71H.96v2.33C2.44 15.98 5.48 18 9 18z" />
          <path fill="#FBBC05" d="M3.97 10.7c-.18-.54-.28-1.11-.28-1.7s.1-1.16.28-1.7V4.97H.96C.35 6.18 0 7.55 0 9s.35 2.82.96 4.03l3.01-2.33z" />
          <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.97l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
        </svg>
        Continue with Google
      </button>
    </>
  );
}
