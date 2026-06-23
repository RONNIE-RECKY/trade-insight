"""Multiple independent trading strategies, each casting a transparent vote.

Rather than one indicator deciding direction, we run several classic strategies
and aggregate their votes — a setup confirmed by trend, momentum AND a pattern
is higher-conviction than one indicator alone. Every vote records its reason,
so the aggregate stays fully explainable (and honest: more agreement ≠ a
guarantee, it just means more confirming evidence).

Each strategy returns: {"name", "signal": bullish|bearish|neutral, "reason"}.
"""
from __future__ import annotations


def _trend_following(sig: dict) -> dict:
    if "ema_20" in sig and "ema_50" in sig and "close" in sig:
        if sig["ema_20"] > sig["ema_50"] and sig["close"] >= sig["ema_20"]:
            return {"name": "Trend-following", "signal": "bullish", "reason": "price above a rising EMA20 > EMA50 stack"}
        if sig["ema_20"] < sig["ema_50"] and sig["close"] <= sig["ema_20"]:
            return {"name": "Trend-following", "signal": "bearish", "reason": "price below a falling EMA20 < EMA50 stack"}
    return {"name": "Trend-following", "signal": "neutral", "reason": "EMAs not aligned with price"}


def _momentum(sig: dict) -> dict:
    if sig.get("macd_bullish_cross") or (sig.get("macd_hist", 0) > 0):
        return {"name": "Momentum (MACD)", "signal": "bullish", "reason": "MACD above signal / positive histogram"}
    if sig.get("macd_bearish_cross") or (sig.get("macd_hist", 0) < 0):
        return {"name": "Momentum (MACD)", "signal": "bearish", "reason": "MACD below signal / negative histogram"}
    return {"name": "Momentum (MACD)", "signal": "neutral", "reason": "no clear MACD momentum"}


def _mean_reversion(sig: dict) -> dict:
    if sig.get("rsi_oversold") or sig.get("price_below_lower_band"):
        return {"name": "Mean-reversion", "signal": "bullish", "reason": "oversold RSI / price below lower Bollinger band"}
    if sig.get("rsi_overbought") or sig.get("price_above_upper_band"):
        return {"name": "Mean-reversion", "signal": "bearish", "reason": "overbought RSI / price above upper Bollinger band"}
    return {"name": "Mean-reversion", "signal": "neutral", "reason": "RSI mid-range, price inside bands"}


def _stochastic(sig: dict) -> dict:
    if sig.get("stoch_oversold"):
        return {"name": "Stochastic", "signal": "bullish", "reason": f"stochastic oversold ({sig.get('stoch_k')})"}
    if sig.get("stoch_overbought"):
        return {"name": "Stochastic", "signal": "bearish", "reason": f"stochastic overbought ({sig.get('stoch_k')})"}
    return {"name": "Stochastic", "signal": "neutral", "reason": "stochastic mid-range"}


def _breakout(sig: dict, patterns: list[dict]) -> dict:
    close = sig.get("close")
    if close is None:
        return {"name": "Breakout", "signal": "neutral", "reason": "no price"}
    resistance = next((p["points"][-1]["price"] for p in patterns if p["pattern"] == "resistance_level"), None)
    support = next((p["points"][-1]["price"] for p in patterns if p["pattern"] == "support_level"), None)
    if resistance is not None and close > resistance:
        return {"name": "Breakout", "signal": "bullish", "reason": f"price broke above resistance {round(resistance, 5)}"}
    if support is not None and close < support:
        return {"name": "Breakout", "signal": "bearish", "reason": f"price broke below support {round(support, 5)}"}
    return {"name": "Breakout", "signal": "neutral", "reason": "trading within range"}


def _pattern_strategy(patterns: list[dict]) -> dict:
    bull = any(p["direction"] == "bullish" for p in patterns)
    bear = any(p["direction"] == "bearish" for p in patterns)
    if bull and not bear:
        return {"name": "Pattern", "signal": "bullish", "reason": "bullish chart pattern (e.g. double bottom)"}
    if bear and not bull:
        return {"name": "Pattern", "signal": "bearish", "reason": "bearish chart pattern (e.g. double top)"}
    return {"name": "Pattern", "signal": "neutral", "reason": "no decisive pattern"}


def evaluate_strategies(sig: dict, patterns: list[dict]) -> dict:
    """Run all strategies and aggregate their votes into a direction + score."""
    strategies = [
        _trend_following(sig),
        _momentum(sig),
        _mean_reversion(sig),
        _stochastic(sig),
        _breakout(sig, patterns),
        _pattern_strategy(patterns),
    ]

    bulls = [s for s in strategies if s["signal"] == "bullish"]
    bears = [s for s in strategies if s["signal"] == "bearish"]

    if len(bulls) > len(bears):
        direction, agreeing = "bullish", bulls
    elif len(bears) > len(bulls):
        direction, agreeing = "bearish", bears
    else:
        direction, agreeing = "neutral", []

    return {
        "direction": direction,
        "confluence_score": len(agreeing),
        "strategies": strategies,
        "factors": [s["name"] for s in agreeing],
        "strategy_agreement": f"{len(agreeing)}/{len(strategies)}",
    }
