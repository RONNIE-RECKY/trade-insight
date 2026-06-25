import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-neutral-800/80 bg-[#0b0f17]">
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2 font-semibold text-neutral-100">
              <span className="inline-block h-2 w-2 rounded-full bg-gradient-to-br from-cyan-400 to-emerald-400" />
              Trade Insight
            </div>
            <p className="mt-2 text-xs text-neutral-500">
              Transparent, backtested market analysis. Not financial advice.
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
          <p className="mt-2">© {new Date().getFullYear()} Trade Insight · Demo build.</p>
        </div>
      </div>
    </footer>
  );
}
