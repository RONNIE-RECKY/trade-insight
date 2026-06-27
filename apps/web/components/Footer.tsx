import Link from "next/link";
import { Logo } from "@/components/Logo";
import { PartnerLogo } from "@/components/PartnerLogo";

// Text-only partners (no logo file). The two with logos render as images.
const TEXT_PARTNERS = ["OANDA", "TradingView", "Finnhub"];

export function Footer() {
  return (
    <footer className="mt-16 border-t border-neutral-800/80 bg-[#0b0f17]">
      <div className="mx-auto max-w-5xl px-4 py-10">
        {/* partners */}
        <div className="mb-10">
          <p className="text-center text-[11px] font-semibold uppercase tracking-widest text-neutral-600">
            Trusted partners
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
            <PartnerLogo src="/partners/hive-konnect.png" name="HIVE Konnect" />
            <PartnerLogo src="/partners/broke-boyz.png" name="Broke Boyz" />
            {TEXT_PARTNERS.map((p) => (
              <span
                key={p}
                className="text-sm font-semibold tracking-wide text-neutral-500 transition-colors hover:text-emerald-400"
              >
                {p}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 border-t border-neutral-800/60 pt-10">
          <div className="col-span-2 sm:col-span-1">
            <Logo />
            <p className="mt-2 text-xs text-neutral-500">
              Multi-strategy, backtested market analysis.
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Product</p>
            <ul className="mt-3 space-y-2 text-sm text-neutral-400">
              <li><Link href="/charts" className="hover:text-neutral-100">Charts</Link></li>
              <li><Link href="/signals" className="hover:text-neutral-100">Signals</Link></li>
              <li><Link href="/pricing" className="hover:text-neutral-100">Pricing</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Account</p>
            <ul className="mt-3 space-y-2 text-sm text-neutral-400">
              <li><Link href="/login" className="hover:text-neutral-100">Log in</Link></li>
              <li><Link href="/signup" className="hover:text-neutral-100">Sign up</Link></li>
              <li><Link href="/account" className="hover:text-neutral-100">My package</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Markets</p>
            <ul className="mt-3 space-y-2 text-sm text-neutral-400">
              <li>Forex majors</li>
              <li>Gold (XAUUSD)</li>
              <li>BTC &amp; ETH</li>
            </ul>
          </div>
        </div>
        <div className="mt-10 border-t border-neutral-800/80 pt-6 text-xs text-neutral-600">
          <p>
            Trading carries risk of loss. Signals and analysis are informational only, generated from
            public technical-analysis rules, and are not financial advice or a guarantee of returns.
          </p>
          <p className="mt-2 flex flex-wrap items-center gap-3">
            <span>© {new Date().getFullYear()} PIP HIVE. Not financial advice.</span>
            <Link href="/terms" className="underline underline-offset-2 hover:text-neutral-400">
              Terms of Service
            </Link>
            <Link href="/privacy" className="underline underline-offset-2 hover:text-neutral-400">
              Privacy Policy
            </Link>
          </p>
        </div>
      </div>
    </footer>
  );
}
