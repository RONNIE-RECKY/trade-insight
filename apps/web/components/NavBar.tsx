"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";

function NavLink({ href, children, onClick }: { href: string; children: React.ReactNode; onClick?: () => void }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`text-sm transition-colors ${
        active ? "text-cyan-400 font-medium" : "text-neutral-400 hover:text-neutral-100"
      }`}
    >
      {children}
    </Link>
  );
}

const PLAN_BADGE: Record<string, string> = {
  free: "text-neutral-400 border-neutral-700",
  pro: "text-sky-300 border-sky-500/40 bg-sky-500/10",
  ultimate: "text-cyan-300 border-cyan-500/40 bg-cyan-500/10",
  platinum: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
};

export function NavBar() {
  const { data: session } = useSession();
  const plan = (session?.user as { plan?: string } | undefined)?.plan ?? "free";
  const [open, setOpen] = useState(false);

  const links = (onClick?: () => void) => (
    <>
      <NavLink href="/charts" onClick={onClick}>Charts</NavLink>
      <NavLink href="/signals" onClick={onClick}>Signals</NavLink>
      <NavLink href="/auto-trade" onClick={onClick}>Auto-Trade</NavLink>
      <NavLink href="/watchlist" onClick={onClick}>Watchlist</NavLink>
      <NavLink href="/pricing" onClick={onClick}>Pricing</NavLink>
    </>
  );

  const authArea = (
    session?.user ? (
      <div className="flex items-center gap-3">
        <Link
          href="/account"
          className={`text-[10px] font-medium uppercase tracking-wide px-2 py-0.5 rounded-full border ${
            PLAN_BADGE[plan] ?? PLAN_BADGE.free
          }`}
        >
          {plan}
        </Link>
        <span className="text-neutral-400 hidden lg:inline">{session.user.email}</span>
        <button
          onClick={() => signOut({ callbackUrl: "/" })}
          className="text-neutral-200 hover:text-neutral-50 underline underline-offset-2 text-sm"
        >
          Log out
        </button>
      </div>
    ) : (
      <div className="flex items-center gap-3">
        <Link href="/login" className="text-neutral-200 hover:text-neutral-50 underline underline-offset-2 text-sm">
          Log in
        </Link>
        <Link
          href="/signup"
          className="rounded-md bg-gradient-to-br from-cyan-500 to-emerald-500 text-neutral-950 font-medium px-3 py-1.5 text-sm"
        >
          Sign up
        </Link>
      </div>
    )
  );

  return (
    <nav className="w-full border-b border-neutral-800/80 bg-[#0d1117]/80 backdrop-blur sticky top-0 z-20">
      <div className="flex items-center justify-between px-4 sm:px-6 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-semibold text-neutral-50 flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-gradient-to-br from-cyan-400 to-emerald-400" />
            Trade Insight
          </Link>
          {/* desktop links */}
          <div className="hidden md:flex items-center gap-6">{links()}</div>
        </div>

        {/* desktop auth */}
        <div className="hidden md:block">{authArea}</div>

        {/* mobile hamburger */}
        <button
          aria-label="Menu"
          onClick={() => setOpen((o) => !o)}
          className="md:hidden flex flex-col gap-1 p-2"
        >
          <span className="block h-0.5 w-5 bg-neutral-300" />
          <span className="block h-0.5 w-5 bg-neutral-300" />
          <span className="block h-0.5 w-5 bg-neutral-300" />
        </button>
      </div>

      {/* mobile menu panel */}
      {open && (
        <div className="md:hidden border-t border-neutral-800/80 px-4 py-4 flex flex-col gap-4">
          <div className="flex flex-col gap-3">{links(() => setOpen(false))}</div>
          <div className="pt-3 border-t border-neutral-800/80">{authArea}</div>
        </div>
      )}
    </nav>
  );
}
