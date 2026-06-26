"""Backtest the confluence-scoring rules over historical candles to produce
a real, reproducible hit-rate — replacing the marketing-style accuracy
numbers seen on sites like pipnex-ai.com.

Method: walk forward through history; at each bar with enough lookback,
recompute indicators+patterns using only data available up to that bar,
score confluence, and if a non-neutral signal fires, check whether price
moved in the predicted direction by at least `move_threshold` within the
next `lookahead` bars. Hit rate = fraction of fired signals that hit.
"""
from __future__ import annotations

import pandas as pd

from .indicators import compute_indicators, indicator_signals_at
from .patterns import patterns_as_of, precompute_swings
from .strategies import evaluate_strategies

MIN_LOOKBACK = 60


def run_backtest(
    df: pd.DataFrame,
    lookahead: int = 5,
    move_threshold: float = 0.005,
    min_confluence: int = 2,
) -> dict:
    if len(df) < MIN_LOOKBACK + lookahead + 1:
        return {
            "total_signals": 0,
            "hits": 0,
            "hit_rate": None,
            "lookahead": lookahead,
            "move_threshold": move_threshold,
            "min_confluence": min_confluence,
            "trades": [],
        }

    # Compute indicators and swing points ONCE over the full series; both are
    # causal (row i depends only on rows <= i), so reading them as-of bar i is
    # equivalent to recomputing on the truncated window, but O(n) instead of O(n^2).
    enriched = compute_indicators(df)
    swings = precompute_swings(df)
    closes = df["close"].astype(float).to_numpy()
    ts_values = df["ts"].astype(str).to_numpy()

    # fetch learned weights once (not per bar) to keep the walk O(n)
    try:
        from .learning import get_weights

        weights = get_weights()
    except Exception:
        weights = {}

    trades = []

    for i in range(MIN_LOOKBACK, len(df) - lookahead):
        ind_signals = indicator_signals_at(enriched, i)
        pats = patterns_as_of(swings, i)
        result = evaluate_strategies(ind_signals, pats, weights)

        if result["direction"] == "neutral" or result["confluence_score"] < min_confluence:
            continue

        entry_price = float(closes[i])
        future_prices = pd.Series(closes[i + 1 : i + 1 + lookahead])

        if result["direction"] == "bullish":
            target = entry_price * (1 + move_threshold)
            hit = bool((future_prices >= target).any())
        else:
            target = entry_price * (1 - move_threshold)
            hit = bool((future_prices <= target).any())

        trades.append(
            {
                "ts": str(ts_values[i]),
                "direction": result["direction"],
                "confluence_score": result["confluence_score"],
                "factors": result["factors"],
                "entry_price": entry_price,
                "hit": hit,
            }
        )

    total = len(trades)
    hits = sum(1 for t in trades if t["hit"])
    hit_rate = round(hits / total, 4) if total else None

    return {
        "total_signals": total,
        "hits": hits,
        "hit_rate": hit_rate,
        "lookahead": lookahead,
        "move_threshold": move_threshold,
        "min_confluence": min_confluence,
        "trades": trades[-20:],  # most recent 20 for inspection
    }
