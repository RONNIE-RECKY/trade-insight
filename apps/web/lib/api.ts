const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Candle = {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type PatternPoint = { ts: string; price: number };
export type Pattern = { pattern: string; direction: string; points: PatternPoint[] };

export type Analysis = {
  symbol: string;
  interval: string;
  direction: string;
  confluence_score: number;
  factors: string[];
  indicator_signals: Record<string, number | boolean>;
  patterns: Pattern[];
};

export type NewsHeadline = { headline: string; score: number; currency_side: "base" | "quote" };

export type TradeLevels = {
  entry: number;
  stop_loss: number;
  take_profit: number;
  risk: number;
  risk_reward: number;
};

export type Signal = {
  id: number;
  symbol: string;
  date: string;
  direction: string;
  confluence_score: number;
  backtest_hit_rate: number | null;
  timeframes_agreed?: string[];
  news_sentiment?: string;
  interval?: string;
  tier?: "premium" | "standard";
  entry?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  risk_reward?: number | null;
  reasoning: {
    factors: string[];
    indicator_signals: Record<string, number | boolean>;
    patterns: Pattern[];
    commentary?: string;
    news_headlines?: NewsHeadline[];
  };
};

export type Prediction = {
  symbol: string;
  interval: string;
  direction: string;
  confluence_score: number;
  factors: string[];
  patterns: Pattern[];
  indicator_signals: Record<string, number | boolean>;
  levels: TradeLevels | null;
  tier: "premium" | "standard";
  news_sentiment: string;
};

export type CurrentPosition = {
  current_price: number;
  period_high: number;
  period_low: number;
  range_position_pct: number | null;
  trend: string;
  above_ema_20: boolean | null;
  above_ema_50: boolean | null;
  ema_20: number | null;
  ema_50: number | null;
  nearest_support: number | null;
  nearest_resistance: number | null;
  distance_to_entry_pct?: number;
  distance_to_stop_pct?: number;
  distance_to_target_pct?: number;
};

export type StrategyVote = { name: string; signal: "bullish" | "bearish" | "neutral"; reason: string };

export type FullAnalysis = {
  symbol: string;
  interval: string;
  direction: string;
  confluence_score: number;
  factors: string[];
  strategies: StrategyVote[];
  strategy_agreement: string;
  patterns: Pattern[];
  levels: TradeLevels | null;
  current_position: CurrentPosition;
  news_sentiment: string;
  news_headlines: NewsHeadline[];
  commentary: string;
  backtest_hit_rate?: number | null;
  backtest_sample_size?: number;
  confidence?: "high" | "medium" | "low";
  high_confidence?: boolean;
  meets_target?: boolean;
  target_accuracy?: number;
  candle_count: number;
};

export type MultiTimeframe = {
  symbol: string;
  direction: string;
  all_agree: boolean;
  timeframes: Record<string, Analysis>;
};

export type AdminOverview = {
  user_count: number;
  signals_today: number;
  signals_total: number;
  data_source: string;
  tracked_symbols: string[];
  last_signal_by_symbol: Record<string, string>;
  candle_cache: Record<string, { candle_count: number; last_ts: string }>;
};

export type AdminUser = { id: number; email: string; is_admin: number; created_at: string };

export type Plan = {
  id: "free" | "pro" | "ultimate" | "platinum";
  name: string;
  price: number;
  rank: number;
  tagline: string;
  highlight?: string;
  popular?: boolean;
  features: string[];
  capabilities?: Record<string, unknown>;
};

// Plan ranks must match billing.py. Used for feature gating in the UI.
export const PLAN_RANK: Record<string, number> = { free: 0, pro: 1, ultimate: 2, platinum: 3 };

export function canSeePremiumSignals(plan?: string) {
  return (PLAN_RANK[plan ?? "free"] ?? 0) >= PLAN_RANK.ultimate;
}

export function canUseIntradayBot(plan?: string) {
  return (PLAN_RANK[plan ?? "free"] ?? 0) >= PLAN_RANK.pro;
}

export function canExport(plan?: string) {
  return (PLAN_RANK[plan ?? "free"] ?? 0) >= PLAN_RANK.pro;
}

export function isFreePlan(plan?: string) {
  return (PLAN_RANK[plan ?? "free"] ?? 0) === 0;
}

export function canAutoTrade(plan?: string) {
  return (PLAN_RANK[plan ?? "free"] ?? 0) >= PLAN_RANK.ultimate;
}

export function hasApiAccess(plan?: string) {
  return (PLAN_RANK[plan ?? "free"] ?? 0) >= PLAN_RANK.platinum;
}

// Daily signal caps per plan (must match billing.py capabilities).
export const PLAN_DAILY_CAP: Record<string, number | null> = {
  free: 1,
  pro: 10,
  ultimate: 40,
  platinum: null, // unlimited
};

export function getApiKey(userId: number) {
  return apiFetch<{ api_key: string }>("/billing/api-key", userHeaders(userId));
}

export type StrategyWeight = { name: string; wins: number; total: number; weight: number };

export function getLearningStats() {
  return apiFetch<{ strategies: StrategyWeight[] }>("/learning/stats");
}

export type AutoTradeSettings = {
  enabled: boolean;
  max_open: number;
  only_high_confidence: boolean;
};

export type AutoTrade = {
  id: number;
  symbol: string;
  interval: string | null;
  direction: string;
  entry: number;
  stop_loss: number;
  take_profit: number;
  status: string;
  outcome: string | null;
  exit_price: number | null;
  pnl_pct: number | null;
  venue?: string;
  broker_ref?: string | null;
  opened_at: string;
  closed_at: string | null;
};

export type AutoTradePositions = {
  open: AutoTrade[];
  closed: AutoTrade[];
  stats: {
    open_count: number;
    closed_count: number;
    wins: number;
    win_rate: number | null;
    total_pnl_pct: number;
  };
};

function userHeaders(userId?: number | null): RequestInit {
  return userId ? { headers: { "X-User-Id": String(userId) } } : {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${body}`);
  }
  return res.json();
}

export function listSymbols() {
  return apiFetch<{ symbols: string[]; data_source: string }>("/symbols");
}

export function getCandles(symbol: string, interval: string = "1day") {
  return apiFetch<{ symbol: string; interval: string; candles: Candle[] }>(
    `/candles/${encodeURIComponent(symbol)}?interval=${interval}`
  );
}

export function getAnalysis(symbol: string, interval: string = "1day") {
  return apiFetch<Analysis>(`/analysis/${encodeURIComponent(symbol)}?interval=${interval}`);
}

export function getMultiTimeframe(symbol: string) {
  return apiFetch<MultiTimeframe>(`/analysis/${encodeURIComponent(symbol)}/multi-timeframe`);
}

export function getPredictions(symbol: string) {
  return apiFetch<{ symbol: string; predictions: Prediction[] }>(
    `/predictions/${encodeURIComponent(symbol)}`
  );
}

export function analyze(symbol: string, interval: string, userId?: number | null) {
  return apiFetch<FullAnalysis>(
    `/analyze/${encodeURIComponent(symbol)}?interval=${interval}`,
    userHeaders(userId)
  );
}

export function exportAnalysisUrl(symbol: string, interval: string, format: "json" | "csv") {
  return `${API_BASE_URL}/analyze/${encodeURIComponent(symbol)}/export?interval=${interval}&format=${format}`;
}

export function getSignalsToday(userId?: number | null, symbol?: string) {
  const q = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return apiFetch<{ signals: Signal[]; plan: string }>(`/signals/today${q}`, userHeaders(userId));
}

export function getSignalsHistory(userId?: number | null) {
  return apiFetch<{ signals: Signal[]; plan: string }>("/signals/history", userHeaders(userId));
}

export function verifyCode(email: string, code: string) {
  return apiFetch<{ ok: boolean; verified: boolean }>("/auth/verify-code", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export function resendCode(email: string) {
  return apiFetch<{ ok: boolean; email_sent?: boolean; verification_code?: string }>("/auth/resend-code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function login(email: string, password: string) {
  return apiFetch<{ id: number; email: string; is_admin: boolean; plan: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signup(email: string, password: string) {
  return apiFetch<{
    id: number;
    email: string;
    is_admin: boolean;
    plan: string;
    verified: boolean;
    verification_code?: string;
    email_sent?: boolean;
  }>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getPlans() {
  return apiFetch<{ plans: Plan[]; payments_enabled: boolean }>("/billing/plans");
}

export function checkout(userId: number, plan: string) {
  return apiFetch<{ url: string }>("/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, plan }),
  });
}

// Admin-only manual grant (support/testing). Normal users go through checkout().
export function adminSetPlan(adminUserId: number, targetUserId: number, plan: string) {
  return apiFetch<{ ok: boolean; plan: string }>("/billing/subscribe", {
    method: "POST",
    headers: { "X-User-Id": String(adminUserId) },
    body: JSON.stringify({ user_id: targetUserId, plan }),
  });
}

export function getAutoTradeSettings(userId: number) {
  return apiFetch<AutoTradeSettings>("/auto-trade/settings", userHeaders(userId));
}

export function updateAutoTradeSettings(userId: number, s: AutoTradeSettings) {
  return apiFetch<AutoTradeSettings>("/auto-trade/settings", {
    method: "POST",
    headers: { "X-User-Id": String(userId) },
    body: JSON.stringify(s),
  });
}

export function getAutoTradePositions(userId: number) {
  return apiFetch<AutoTradePositions>("/auto-trade/positions", userHeaders(userId));
}

export type BrokerConnection = {
  provider: string;
  mode: string;
  account_id?: string | null;
  connected: boolean;
  risk_acknowledged: boolean;
  has_token?: boolean;
};

export function getBroker(userId: number) {
  return apiFetch<BrokerConnection>("/auto-trade/broker", userHeaders(userId));
}

export function connectBroker(
  userId: number,
  body: { provider: string; mode: string; account_id?: string; token?: string; risk_acknowledged?: boolean }
) {
  return apiFetch<BrokerConnection>("/auto-trade/broker", {
    method: "POST",
    headers: { "X-User-Id": String(userId) },
    body: JSON.stringify(body),
  });
}

function adminHeaders(userId: number): RequestInit {
  return { headers: { "X-User-Id": String(userId) } };
}

export function getAdminOverview(userId: number) {
  return apiFetch<AdminOverview>("/admin/overview", adminHeaders(userId));
}

export function getAdminUsers(userId: number) {
  return apiFetch<{ users: AdminUser[] }>("/admin/users", adminHeaders(userId));
}

export function getAdminSignals(userId: number) {
  return apiFetch<{ signals: Signal[] }>("/admin/signals", adminHeaders(userId));
}

export function getWatchlist(userId: number) {
  return apiFetch<{ symbols: string[] }>(`/watchlist/${userId}`);
}

export function addWatchlistItem(userId: number, symbol: string) {
  return apiFetch<{ ok: boolean }>("/watchlist", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, symbol }),
  });
}

export function removeWatchlistItem(userId: number, symbol: string) {
  return apiFetch<{ ok: boolean }>("/watchlist", {
    method: "DELETE",
    body: JSON.stringify({ user_id: userId, symbol }),
  });
}
