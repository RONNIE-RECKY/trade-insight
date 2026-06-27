import Link from "next/link";

export const metadata = { title: "Privacy Policy — PIP HIVE" };

export default function PrivacyPage() {
  return (
    <div className="prose prose-invert max-w-2xl mx-auto space-y-6 text-sm leading-relaxed text-neutral-300">
      <div>
        <h1 className="text-2xl font-bold text-neutral-100">Privacy Policy</h1>
        <p className="text-xs text-neutral-500 mt-1">Last updated: {new Date().toISOString().slice(0, 10)}</p>
      </div>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">1. What we collect</h2>
        <ul className="list-disc list-inside space-y-1">
          <li>Account details you provide: full name, phone number, email address, password (stored as a salted hash, never in plain text).</li>
          <li>Usage data: your watchlist, signal/chart views, uploaded chart images (if your plan includes uploads), and auto-trade bot settings and history.</li>
          <li>If you connect a brokerage account for the automated bot, the account ID and API token you provide — used only to place/track orders on your behalf with that broker.</li>
          <li>Billing data: handled by our payment processor (Stripe); we do not store your full card number.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">2. How we use it</h2>
        <p>
          To run your account, generate and gate signals by your plan, operate the automated bot you configure,
          send account/verification emails, process payments, and improve the service (e.g. measuring which
          strategies perform well, in aggregate).
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">3. Uploaded charts</h2>
        <p>
          Chart images you upload are processed to extract candle/price data for analysis. They are stored
          only as needed to provide the feature and enforce your plan&apos;s monthly upload limit.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">4. Brokerage credentials</h2>
        <p>
          Broker API tokens you provide for demo or live trading are stored to let the bot place and monitor
          orders. We do not sell or share this data. You can disconnect your broker account at any time.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">5. Third parties</h2>
        <p>
          We use third-party services to operate PIP HIVE: market data providers (e.g. Twelve Data, Yahoo
          Finance), news data (e.g. Finnhub), email delivery, payment processing (Stripe), and hosting
          (Railway). Each handles data under their own privacy practices.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">6. Data retention &amp; deletion</h2>
        <p>
          We keep account data while your account is active. You can request deletion of your account and
          associated data at any time by contacting support.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">7. Security</h2>
        <p>
          Passwords are hashed (never stored in plain text). We restrict access to stored brokerage tokens to
          what the bot needs to operate. No system is perfectly secure; use a unique password for your account.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-neutral-100">8. Your rights</h2>
        <p>You may request a copy of, correction to, or deletion of your personal data at any time.</p>
      </section>

      <p className="pt-4">
        <Link href="/terms" className="text-emerald-400 underline underline-offset-2">
          Terms of Service
        </Link>{" "}
        ·{" "}
        <Link href="/" className="text-emerald-400 underline underline-offset-2">
          Back to home
        </Link>
      </p>
    </div>
  );
}
