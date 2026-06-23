"""Transparent confluence scoring: combine indicator signals + detected
patterns into a score with a human-readable breakdown of what triggered.

No fabricated accuracy percentage is produced here. Historical hit-rate
comes only from backtest.py, run over real price history.
"""
from __future__ import annotations

_BULLISH_INDICATOR_KEYS = ["rsi_oversold", "macd_bullish_cross", "ema_bullish_cross", "price_below_lower_band"]
_BEARISH_INDICATOR_KEYS = ["rsi_overbought", "macd_bearish_cross", "ema_bearish_cross", "price_above_upper_band"]


def score_confluence(indicator_signals: dict, patterns: list[dict]) -> dict:
    bullish_factors = [k for k in _BULLISH_INDICATOR_KEYS if indicator_signals.get(k)]
    bearish_factors = [k for k in _BEARISH_INDICATOR_KEYS if indicator_signals.get(k)]

    for p in patterns:
        if p["direction"] == "bullish":
            bullish_factors.append(p["pattern"])
        elif p["direction"] == "bearish":
            bearish_factors.append(p["pattern"])

    bullish_score = len(bullish_factors)
    bearish_score = len(bearish_factors)

    if bullish_score == 0 and bearish_score == 0:
        direction = "neutral"
    elif bullish_score >= bearish_score:
        direction = "bullish"
    else:
        direction = "bearish"

    score = max(bullish_score, bearish_score)
    factors = bullish_factors if direction == "bullish" else bearish_factors

    return {
        "direction": direction,
        "confluence_score": score,
        "factors": factors,
        "indicator_signals": indicator_signals,
        "patterns": patterns,
    }
