"""Price-structure strategies that need the candle series (not just the latest
indicator snapshot): market structure, psychological (round-number) levels,
Fibonacci retracement, trendline, and candlestick patterns.

Each casts the same transparent {name, signal, reason} vote as the indicator
strategies in strategies.py, so they slot straight into the weighted consensus
and the adaptive learning weights apply to them too.

They read only the most recent `lookback` bars, which keeps them (a) focused on
current structure — which is what these methods are about — and (b) cheap and
causal, so the backtest can vote with the exact same rules per bar without going
quadratic. Every one returns a neutral vote when its condition isn't clearly met
(a no-read is honest; forcing a direction is not).
"""
from __future__ import annotations

import pandas as pd

from .patterns import find_swing_points

LOOKBACK = 60


def _round_step(price: float) -> float:
    """The spacing between 'round number' psychological levels for a price of
    this magnitude (gold trades in $50 handles, FX majors in 100-pip figures)."""
    if price >= 500:      # gold / indices
        return 50.0
    if price >= 100:      # e.g. USDJPY ~150
        return 1.0
    if price >= 10:
        return 1.0
    return 0.01           # FX majors ~1.08, 0.66 → the "00/50" big figures


class _Swings:
    """Swing highs/lows computed ONCE per evaluation and shared by every
    structure strategy (they'd otherwise each recompute pivots)."""

    def __init__(self, df: pd.DataFrame):
        swung = find_swing_points(df, window=3)
        hi_pos = swung.index[swung["swing_high"]].to_list()
        lo_pos = swung.index[swung["swing_low"]].to_list()
        self.high_pts = [(int(p), float(swung.at[p, "high"])) for p in hi_pos]
        self.low_pts = [(int(p), float(swung.at[p, "low"])) for p in lo_pos]
        self.highs = [v for _, v in self.high_pts]
        self.lows = [v for _, v in self.low_pts]
        self.last_high_pos = hi_pos[-1] if hi_pos else -1
        self.last_low_pos = lo_pos[-1] if lo_pos else -1


def _market_structure(df: pd.DataFrame, sw: _Swings) -> dict:
    """Higher-highs + higher-lows = bullish structure; lower-highs + lower-lows
    = bearish. A break of that structure (price taking out the last opposing
    swing) is the classic 'break of structure' confirmation."""
    highs, lows = sw.highs, sw.lows
    if len(highs) < 2 or len(lows) < 2:
        return {"name": "Market structure", "signal": "neutral", "reason": "not enough swings to read structure"}
    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]
    lh = highs[-1] < highs[-2]
    ll = lows[-1] < lows[-2]
    if hh and hl:
        return {"name": "Market structure", "signal": "bullish", "reason": "higher highs and higher lows (bullish structure)"}
    if lh and ll:
        return {"name": "Market structure", "signal": "bearish", "reason": "lower highs and lower lows (bearish structure)"}
    return {"name": "Market structure", "signal": "neutral", "reason": "structure mixed / ranging"}


def _psychological_level(df: pd.DataFrame) -> dict:
    """React to round-number levels. If price just reclaimed a round level from
    below (holding it as support) → bullish; if it was rejected from above
    (capped as resistance) → bearish. Only fires when price is genuinely near a
    level (within ~15% of the level spacing)."""
    close = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2]) if len(df) >= 2 else close
    step = _round_step(close)
    nearest = round(close / step) * step
    dist = abs(close - nearest)
    if dist > step * 0.15:
        return {"name": "Psychological level", "signal": "neutral", "reason": "price not near a round level"}
    # crossed up through the level → support reclaim; down through → rejection
    if prev < nearest <= close:
        return {"name": "Psychological level", "signal": "bullish", "reason": f"reclaimed round level {nearest:g} as support"}
    if prev > nearest >= close:
        return {"name": "Psychological level", "signal": "bearish", "reason": f"rejected at round level {nearest:g}"}
    # sitting on the level: bias by which side it's holding
    if close >= nearest:
        return {"name": "Psychological level", "signal": "bullish", "reason": f"holding above round level {nearest:g}"}
    return {"name": "Psychological level", "signal": "bearish", "reason": f"capped below round level {nearest:g}"}


def _fibonacci(df: pd.DataFrame, sw: _Swings) -> dict:
    """Fibonacci retracement of the most recent swing leg. In an up-leg (swing
    low → swing high), a pullback into the 0.5–0.618 zone that holds is a
    bullish continuation entry; symmetrically for a down-leg."""
    if not sw.highs or not sw.lows:
        return {"name": "Fibonacci", "signal": "neutral", "reason": "no swing leg to measure"}
    swing_high = sw.highs[-1]
    swing_low = sw.lows[-1]
    close = float(df["close"].iloc[-1])
    leg = swing_high - swing_low
    if leg <= 0:
        return {"name": "Fibonacci", "signal": "neutral", "reason": "degenerate swing leg"}

    up_leg = sw.last_high_pos > sw.last_low_pos  # high formed after low → up-leg

    fib_50 = swing_high - 0.5 * leg if up_leg else swing_low + 0.5 * leg
    fib_618 = swing_high - 0.618 * leg if up_leg else swing_low + 0.618 * leg
    lo, hi = sorted([fib_50, fib_618])
    in_zone = lo - 0.1 * leg <= close <= hi + 0.1 * leg
    if not in_zone:
        return {"name": "Fibonacci", "signal": "neutral", "reason": "price not in the 0.5–0.618 retracement zone"}
    if up_leg:
        return {"name": "Fibonacci", "signal": "bullish", "reason": "pullback into the 0.5–0.618 retracement of an up-leg"}
    return {"name": "Fibonacci", "signal": "bearish", "reason": "pullback into the 0.5–0.618 retracement of a down-leg"}


def _trendline(df: pd.DataFrame, sw: _Swings) -> dict:
    """Fit a line through recent swing lows (support line) and swing highs
    (resistance line). A rising support line with price above it = bullish
    trend; a falling resistance line with price below it = bearish."""
    low_pts = sw.low_pts
    high_pts = sw.high_pts
    close = float(df["close"].iloc[-1])

    def slope(points: list[tuple[int, float]]) -> float | None:
        if len(points) < 2:
            return None
        (x1, y1), (x2, y2) = points[-2], points[-1]
        if x2 == x1:
            return None
        return (y2 - y1) / (x2 - x1)

    low_slope = slope(low_pts)
    high_slope = slope(high_pts)

    if low_slope is not None and low_slope > 0 and close > low_pts[-1][1]:
        return {"name": "Trendline", "signal": "bullish", "reason": "price riding a rising support trendline"}
    if high_slope is not None and high_slope < 0 and close < high_pts[-1][1]:
        return {"name": "Trendline", "signal": "bearish", "reason": "price under a falling resistance trendline"}
    return {"name": "Trendline", "signal": "neutral", "reason": "no clean trendline read"}


def _candlestick(df: pd.DataFrame) -> dict:
    """Classic single/two-bar candlestick signals on the latest bar: bullish/
    bearish engulfing, hammer, shooting star, doji."""
    if len(df) < 2:
        return {"name": "Candlestick", "signal": "neutral", "reason": "not enough bars"}
    o, h, l, c = (float(df[k].iloc[-1]) for k in ("open", "high", "low", "close"))
    po, pc = float(df["open"].iloc[-2]), float(df["close"].iloc[-2])
    rng = h - l
    if rng <= 0:
        return {"name": "Candlestick", "signal": "neutral", "reason": "flat bar"}
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    # engulfing
    if c > o and pc < po and c >= po and o <= pc:
        return {"name": "Candlestick", "signal": "bullish", "reason": "bullish engulfing"}
    if c < o and pc > po and c <= po and o >= pc:
        return {"name": "Candlestick", "signal": "bearish", "reason": "bearish engulfing"}
    # hammer: small body up top, long lower wick
    if lower_wick >= 2 * body and upper_wick <= body and c >= o:
        return {"name": "Candlestick", "signal": "bullish", "reason": "hammer (long lower wick rejection)"}
    # shooting star: small body low, long upper wick
    if upper_wick >= 2 * body and lower_wick <= body and c <= o:
        return {"name": "Candlestick", "signal": "bearish", "reason": "shooting star (long upper wick rejection)"}
    # doji: indecision
    if body <= rng * 0.1:
        return {"name": "Candlestick", "signal": "neutral", "reason": "doji (indecision)"}
    return {"name": "Candlestick", "signal": "neutral", "reason": "no decisive candlestick"}


def evaluate_structure_strategies(df: pd.DataFrame, lookback: int = LOOKBACK) -> list[dict]:
    """Run all five price-structure strategies on the most recent `lookback`
    bars. Returns their votes; empty list if there aren't enough bars."""
    if df is None or len(df) < 5:
        return []
    window = df.tail(lookback).reset_index(drop=True)
    sw = _Swings(window)  # compute pivots once, share across strategies
    return [
        _market_structure(window, sw),
        _psychological_level(window),
        _fibonacci(window, sw),
        _trendline(window, sw),
        _candlestick(window),
    ]
