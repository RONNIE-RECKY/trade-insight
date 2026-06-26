/** PIP HIVE brand mark — a honeycomb hive cluster in green + wordmark. */
export function Logo({ className = "", showText = true }: { className?: string; showText?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg width="30" height="30" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
        <defs>
          <linearGradient id="hiveg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop stopColor="#34d399" />
            <stop offset="1" stopColor="#16a34a" />
          </linearGradient>
        </defs>
        {/* honeycomb hexagons */}
        <path d="M24 4l7 4v8l-7 4-7-4V8z" fill="url(#hiveg)" />
        <path d="M13 16l7 4v8l-7 4-7-4v-8z" fill="#16a34a" opacity="0.85" />
        <path d="M35 16l7 4v8l-7 4-7-4v-8z" fill="#22c55e" opacity="0.85" />
        <path d="M24 28l7 4v8l-7 4-7-4v-8z" fill="url(#hiveg)" />
        {/* bee dot accents */}
        <circle cx="24" cy="12" r="2" fill="#0a0e14" />
        <circle cx="24" cy="36" r="2" fill="#0a0e14" />
      </svg>
      {showText && (
        <span className="text-lg font-extrabold tracking-tight">
          <span className="text-neutral-50">PIP</span>
          <span className="bg-gradient-to-r from-emerald-400 to-green-500 bg-clip-text text-transparent"> HIVE</span>
        </span>
      )}
    </span>
  );
}
