import Link from "next/link";

export const metadata = { title: "Terms of Service — PIP HIVE" };

export default function TermsPage() {
  return (
    <div className="prose prose-invert max-w-2xl mx-auto space-y-6 text-sm leading-relaxed text-neutral-300">
      <div>
        <h1 className="text-2xl font-bold text-neutral-100">Terms of Service</h1>
        <p className="text-xs text-neutral-500 mt-1">Last updated: {new Date().toISOString().slice(0, 10)}</p>
      </div>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">1. What PIP HIVE is</h2>
        <p>
          PIP HIVE provides automated technical analysis of forex, gold and crypto markets — chart pattern
          detection, multi-strategy signals, and an optional automated paper-trading bot. It is an
          <strong> informational and educational tool</strong>, not a licensed financial advisor, broker, or
          fund manager.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">2. Not financial advice</h2>
        <p>
          Nothing on this platform — signals, analysis, confidence labels, backtest results, or commentary —
          is financial advice or a recommendation to buy or sell any instrument. Trading carries a real risk
          of loss, up to and including your entire account balance. Past or backtested performance does not
          guarantee future results. You are solely responsible for your own trading decisions.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">3. The automated trading bot</h2>
        <p>
          The bot can run in a <strong>simulated</strong> mode (no real money) or connect to a{" "}
          <strong>demo brokerage account</strong> (real order execution, but on practice/fake funds). If you
          connect a <strong>live</strong> brokerage account, the platform does not place orders automatically —
          you must confirm every trade yourself. PIP HIVE is not liable for losses incurred through any
          connected account, demo or live, including losses caused by software errors, connectivity issues, or
          broker-side problems.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">4. Accounts</h2>
        <p>
          You must provide accurate information at signup (including your name, phone number, and a valid
          email) and keep your login credentials secure. You are responsible for all activity under your
          account.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">5. Subscriptions and billing</h2>
        <p>
          Paid plans renew on a recurring basis. Upgrading to a higher plan takes effect immediately upon
          successful payment. Downgrading or cancelling takes effect at the end of your current billing
          period — you keep your existing plan&apos;s features until then, and no partial refunds are issued
          for the remainder of a paid period unless required by law.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">6. Chart uploads</h2>
        <p>
          If your plan includes chart upload analysis, uploaded images are processed to extract price data and
          run through the same rule-based analysis engine used elsewhere on the platform. Monthly upload
          limits apply per plan as shown on the pricing page.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">7. Acceptable use</h2>
        <p>
          Don&apos;t attempt to circumvent plan limits, resell access, reverse-engineer the service, or use it
          for unlawful purposes. We may suspend or terminate accounts that violate these terms.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">8. Changes</h2>
        <p>We may update these terms from time to time. Continued use of the platform means you accept the current version.</p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">9. Contact</h2>
        <p>Questions about these terms can be sent through the contact details on our account/support pages.</p>
      </section>

      <p className="pt-4">
        <Link href="/privacy" className="text-emerald-400 underline underline-offset-2">
          Privacy Policy
        </Link>{" "}
        ·{" "}
        <Link href="/" className="text-emerald-400 underline underline-offset-2">
          Back to home
        </Link>
      </p>
    </div>
  );
}
