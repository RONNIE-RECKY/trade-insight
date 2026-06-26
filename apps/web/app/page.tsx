"use client";

import Link from "next/link";
import { Pricing } from "@/components/Pricing";

const FAQ = [
  {
    q: "Is this financial advice?",
    a: "No. Everything here is informational analysis built from public technical-analysis rules. You make your own decisions, and trading carries real risk of loss.",
  },
  {
    q: "Where do the win-rates come from?",
    a: "Each signal is backtested by replaying its exact rule over historical candles on that timeframe. The percentage shown is that real historical result — never a marketing figure.",
  },
  {
    q: "Can I cancel my plan?",
    a: "Yes, you can switch or downgrade at any time from your account page. In this demo build, checkout is simulated and no card is charged.",
  },
  {
    q: "Which markets are covered?",
    a: "Ten instruments: the major forex pairs, gold (XAUUSD), plus BTC and ETH — each analyzed across six timeframes from 5 minutes to daily.",
  },
];

const MARKETS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "ETHUSD", "AUDUSD", "USDCAD"];

function ChartGlyph() {
  const candles = [
    [40, 18, 60], [55, 30, 70], [48, 22, 64], [62, 40, 80], [70, 50, 88],
    [60, 38, 74], [78, 58, 92], [85, 64, 100], [74, 52, 90], [92, 70, 108],
  ];
  return (
    <svg viewBox="0 0 240 130" className="w-full" xmlns="http://www.w3.org/2000/svg">
      <line x1="8" y1="40" x2="232" y2="40" stroke="#34d399" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />
      <line x1="8" y1="92" x2="232" y2="92" stroke="#fb7185" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />
      {candles.map(([o, l, h], i) => {
        const x = 12 + i * 22;
        const up = i % 3 !== 1;
        const color = up ? "#34d399" : "#fb7185";
        const bodyTop = Math.min(o, h - 14);
        return (
          <g key={i}>
            <line x1={x} y1={130 - h} x2={x} y2={130 - l} stroke={color} strokeWidth="1.5" />
            <rect x={x - 5} y={130 - bodyTop - 16} width="10" height="16" rx="1.5" fill={color} />
          </g>
        );
      })}
      <line x1="8" y1="64" x2="232" y2="52" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="4 3" />
    </svg>
  );
}

function ProductMockup() {
  return (
    <div className="relative mx-auto w-full max-w-md">
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-tr from-cyan-500/20 to-emerald-500/10 blur-2xl" />
      <div className="relative rounded-2xl border border-neutral-700/80 bg-neutral-900/80 shadow-2xl backdrop-blur">
        <div className="flex items-center gap-1.5 border-b border-neutral-800 px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
          <span className="ml-3 text-xs font-mono text-neutral-500">XAUUSD · 1H</span>
          <span className="ml-auto text-[10px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-2 py-0.5">
            bullish
          </span>
        </div>
        <div className="px-4 pt-4">
          <ChartGlyph />
        </div>
        <div className="grid grid-cols-3 gap-2 px-4 pb-4 pt-2">
          {[
            { l: "Entry", v: "4,172.9", c: "text-sky-400" },
            { l: "Stop", v: "4,138.7", c: "text-rose-400" },
            { l: "Target", v: "4,241.3", c: "text-emerald-400" },
          ].map((cell) => (
            <div key={cell.l} className="rounded-lg border border-neutral-800 bg-neutral-950/60 px-2 py-1.5">
              <p className="text-[10px] text-neutral-500">{cell.l}</p>
              <p className={`text-xs font-mono font-semibold ${cell.c}`}>{cell.v}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-neutral-800 px-4 py-3">
          <p className="text-[11px] text-neutral-400">
            <span className="text-cyan-300">5/6 strategies</span> agree · backtested hit-rate shown per signal
          </p>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  {
    title: "Every timeframe, 5M to 1D",
    body: "We analyze 5-minute, 15m, 30m, 1h, 4h and daily candles for every market — so you see the setup on your timeframe, not just one.",
    tag: "TF",
  },
  {
    title: "Entry, stop-loss & take-profit",
    body: "Each signal comes with concrete levels derived from ATR and market structure, plus a stated risk:reward — no vague 'buy now' calls.",
    tag: "SL",
  },
  {
    title: "Real backtested hit-rates",
    body: "Every signal shows its own walk-forward backtested hit-rate on that exact rule. Not a marketing number — the actual historical result.",
    tag: "%",
  },
  {
    title: "Multi-timeframe confluence",
    body: "Premium signals only fire when 1h, 4h and daily agree and news sentiment doesn't contradict — higher conviction, clearly labelled.",
    tag: "MTF",
  },
  {
    title: "Plain-English analysis",
    body: "An AI-style breakdown explains why each setup fired — built strictly from the underlying indicators, patterns and headlines.",
    tag: "AI",
  },
  {
    title: "Six strategies, one verdict",
    body: "Trend-following, momentum, mean-reversion, stochastic, breakout and pattern strategies each vote — the more that agree, the higher the conviction.",
    tag: "6x",
  },
];

const STEPS = [
  { n: "1", title: "Pick a market", body: "Choose from 10 forex, gold and crypto instruments." },
  { n: "2", title: "Read the confluence", body: "See indicators, patterns and news line up across timeframes." },
  { n: "3", title: "Get a trade plan", body: "Entry, stop, target and the rule's real backtested hit-rate." },
];

export default function LandingPage() {
  return (
    <div className="space-y-24 pb-16">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl border border-neutral-800 bg-gradient-to-b from-neutral-900/80 to-neutral-950 px-6 py-16 sm:py-20">
        <div className="pointer-events-none absolute inset-0 opacity-40 [background:radial-gradient(70%_60%_at_70%_0%,rgba(56,189,248,0.22),transparent),radial-gradient(50%_50%_at_0%_100%,rgba(52,211,153,0.14),transparent)]" />
        <div className="relative grid items-center gap-10 lg:grid-cols-2">
          <div className="text-center lg:text-left">
            <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
              AI-assisted market analysis
            </span>
            <h1 className="mt-6 text-4xl font-bold tracking-tight text-neutral-50 sm:text-5xl">
              Trade ideas you can{" "}
              <span className="bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">
                actually verify
              </span>
            </h1>
            <p className="mt-5 max-w-xl text-base text-neutral-400 sm:text-lg lg:mx-0 mx-auto">
              Forex, gold and crypto signals across six timeframes — each one combining{" "}
              <span className="text-neutral-200">six trading strategies</span> with concrete entry, stop-loss
              and take-profit levels and its own <span className="text-neutral-200">real backtested hit-rate</span>.
            </p>
            <div className="mt-8 flex items-center justify-center gap-3 lg:justify-start">
              <Link
                href="/signals"
                className="rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-neutral-950"
              >
                View today&apos;s signals
              </Link>
              <Link
                href="/pricing"
                className="rounded-lg border border-neutral-700 px-5 py-2.5 text-sm font-medium text-neutral-200 hover:border-neutral-500"
              >
                See packages
              </Link>
            </div>
          </div>
          <ProductMockup />
        </div>

        {/* markets strip */}
        <div className="relative mt-12 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 border-t border-neutral-800/80 pt-6 text-xs font-mono text-neutral-500">
          <span className="text-neutral-600">Live coverage:</span>
          {MARKETS.map((m) => (
            <span key={m} className="text-neutral-400">{m}</span>
          ))}
        </div>
      </section>

      {/* Stats — honest, verifiable */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { value: "10", label: "Markets covered" },
          { value: "6", label: "Timeframes (5M–1D)" },
          { value: "100%", label: "Signals backtested" },
          { value: "0", label: "Guaranteed returns" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5 text-center">
            <p className="bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-3xl font-bold text-transparent">
              {s.value}
            </p>
            <p className="mt-1 text-xs text-neutral-500">{s.label}</p>
          </div>
        ))}
      </section>

      {/* Dashboard snapshot */}
      <section>
        <h2 className="text-center text-2xl font-bold text-neutral-100">Your dashboard at a glance</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-neutral-500">
          Live charts, multi-strategy signals with entry/stop/target, and an automated bot — all in one place.
        </p>
        <div className="mx-auto mt-8 max-w-3xl rounded-2xl border border-neutral-800 bg-neutral-900/60 p-3 shadow-2xl">
          <div className="flex items-center gap-1.5 px-2 py-2">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
            <span className="ml-3 text-xs font-mono text-neutral-500">pip-hive · dashboard</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 p-2">
            <div className="sm:col-span-2 rounded-xl border border-neutral-800 bg-neutral-950/60 p-3">
              <ChartGlyph />
            </div>
            <div className="space-y-2">
              {[
                { s: "XAUUSD", d: "bullish", c: "text-emerald-400" },
                { s: "EURUSD", d: "bearish", c: "text-rose-400" },
                { s: "BTCUSD", d: "bullish", c: "text-emerald-400" },
              ].map((row) => (
                <div key={row.s} className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-neutral-200">{row.s}</span>
                    <span className={row.c}>{row.d}</span>
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-neutral-500">E · SL · TP set</div>
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 p-2">
            {[
              { l: "Win rate", v: "backtested" },
              { l: "Strategies", v: "6 / vote" },
              { l: "Auto-bot", v: "running" },
            ].map((k) => (
              <div key={k.l} className="rounded-lg border border-neutral-800 bg-neutral-950/60 px-3 py-2 text-center">
                <p className="text-[10px] text-neutral-500">{k.l}</p>
                <p className="text-xs font-semibold text-emerald-400">{k.v}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section>
        <h2 className="text-center text-2xl font-bold text-neutral-100">What&apos;s under the hood</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-neutral-500">
          Transparent, rule-based technical analysis — every output traceable to the data behind it.
        </p>
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="group rounded-2xl border border-neutral-800 bg-neutral-900/40 p-6 transition-all hover:border-cyan-500/40 hover:bg-neutral-900/70"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/15 to-emerald-500/10 text-sm font-bold text-cyan-300">
                {f.tag}
              </div>
              <h3 className="mt-4 font-semibold text-neutral-100">{f.title}</h3>
              <p className="mt-2 text-sm text-neutral-400">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section>
        <h2 className="text-center text-2xl font-bold text-neutral-100">How it works</h2>
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-6">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-emerald-500 text-sm font-bold text-neutral-950">
                {s.n}
              </div>
              <h3 className="mt-4 font-semibold text-neutral-100">{s.title}</h3>
              <p className="mt-2 text-sm text-neutral-400">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing">
        <h2 className="text-center text-2xl font-bold text-neutral-100">Choose your package</h2>
        <p className="mx-auto mt-2 mb-10 max-w-xl text-center text-sm text-neutral-500">
          Paid plans unlock the full bot — every timeframe, premium multi-timeframe signals and full
          backtest history. Upgrade or cancel anytime.
        </p>
        <Pricing />
      </section>

      {/* FAQ */}
      <section>
        <h2 className="text-center text-2xl font-bold text-neutral-100">Questions</h2>
        <div className="mx-auto mt-8 max-w-2xl space-y-3">
          {FAQ.map((item) => (
            <div key={item.q} className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5">
              <h3 className="font-semibold text-neutral-100">{item.q}</h3>
              <p className="mt-2 text-sm text-neutral-400">{item.a}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Honesty / differentiator */}
      <section className="rounded-3xl border border-amber-500/20 bg-amber-500/5 p-8 text-center">
        <h2 className="text-xl font-bold text-amber-200">Built to be honest</h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-amber-100/80">
          Trading is risky and most signals lose sometimes. We don&apos;t hide that. There are no
          fabricated &ldquo;98% accuracy&rdquo; claims here — every signal shows the real, backtested
          result of its own rule, and you can inspect exactly why it fired. This is analysis to inform
          your decisions, not financial advice or a promise of profit.
        </p>
        <Link
          href="/signup"
          className="mt-6 inline-block rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-neutral-950"
        >
          Create a free account
        </Link>
      </section>
    </div>
  );
}
