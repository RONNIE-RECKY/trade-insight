"""Rule-based chart pattern detection on swing highs/lows.

These are explicit geometric rules, not a black-box model — every
detection in `detect_patterns` documents which pivots and thresholds
triggered it, so the resulting signal reasoning is auditable.
"""
from __future__ import annotations

import pandas as pd


def find_swing_points(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """Mark local swing highs/lows: a bar whose high/low is the extreme
    within +/- `window` bars.

    Vectorised via a centred rolling window (equivalent to the original
    per-bar scan but O(n) instead of O(n*window)), which matters because the
    backtest and the price-structure strategies call this on every bar."""
    out = df.copy()
    n = len(out)
    size = 2 * window + 1
    if n < size:
        out["swing_high"] = False
        out["swing_low"] = False
        return out

    roll_max = out["high"].rolling(size, center=True).max()
    roll_min = out["low"].rolling(size, center=True).min()
    out["swing_high"] = (out["high"] >= roll_max) & roll_max.notna()
    out["swing_low"] = (out["low"] <= roll_min) & roll_min.notna()
    # the first/last `window` bars can't be centred pivots
    if window > 0:
        out.iloc[:window, out.columns.get_loc("swing_high")] = False
        out.iloc[:window, out.columns.get_loc("swing_low")] = False
        out.iloc[n - window :, out.columns.get_loc("swing_high")] = False
        out.iloc[n - window :, out.columns.get_loc("swing_low")] = False

    return out


def detect_patterns(df: pd.DataFrame, window: int = 3, tolerance: float = 0.0015) -> list[dict]:
    """Detect double top/bottom and basic support/resistance from recent swings.

    `tolerance` is the relative price difference allowed between two swing
    points to still count as "the same level" (e.g. 0.0015 = 0.15%).
    """
    if len(df) < window * 4:
        return []

    swung = find_swing_points(df, window=window)
    highs = [(str(r["ts"]), float(r["high"])) for _, r in swung[swung["swing_high"]].iterrows()]
    lows = [(str(r["ts"]), float(r["low"])) for _, r in swung[swung["swing_low"]].iterrows()]
    return _patterns_from_swings(highs, lows, tolerance)


def _patterns_from_swings(highs: list[tuple], lows: list[tuple], tolerance: float) -> list[dict]:
    """Build the pattern list from ordered (ts, price) swing highs/lows.
    Shared by the live one-shot path and the backtest's per-bar path."""
    detected: list[dict] = []

    # Double top: two most recent swing highs within tolerance of each other.
    if len(highs) >= 2:
        (h1_ts, h1_p), (h2_ts, h2_p) = highs[-2], highs[-1]
        if abs(h1_p - h2_p) / h1_p <= tolerance:
            detected.append(
                {
                    "pattern": "double_top",
                    "direction": "bearish",
                    "points": [{"ts": h1_ts, "price": h1_p}, {"ts": h2_ts, "price": h2_p}],
                }
            )

    # Double bottom: two most recent swing lows within tolerance of each other.
    if len(lows) >= 2:
        (l1_ts, l1_p), (l2_ts, l2_p) = lows[-2], lows[-1]
        if abs(l1_p - l2_p) / l1_p <= tolerance:
            detected.append(
                {
                    "pattern": "double_bottom",
                    "direction": "bullish",
                    "points": [{"ts": l1_ts, "price": l1_p}, {"ts": l2_ts, "price": l2_p}],
                }
            )

    # Simple resistance/support: most recent swing high/low acts as a level.
    if highs:
        detected.append(
            {"pattern": "resistance_level", "direction": "neutral", "points": [{"ts": highs[-1][0], "price": highs[-1][1]}]}
        )
    if lows:
        detected.append(
            {"pattern": "support_level", "direction": "neutral", "points": [{"ts": lows[-1][0], "price": lows[-1][1]}]}
        )

    return detected


def precompute_swings(df: pd.DataFrame, window: int = 3) -> dict:
    """Run swing detection once over the full series. Returns position-tagged
    swing highs/lows so a backtest can ask 'which swings were confirmed as of
    bar i' without re-scanning the window each step."""
    swung = find_swing_points(df, window=window)
    highs = [(pos, str(swung.iloc[pos]["ts"]), float(swung.iloc[pos]["high"])) for pos in range(len(swung)) if swung.iloc[pos]["swing_high"]]
    lows = [(pos, str(swung.iloc[pos]["ts"]), float(swung.iloc[pos]["low"])) for pos in range(len(swung)) if swung.iloc[pos]["swing_low"]]
    return {"highs": highs, "lows": lows, "window": window}


def patterns_as_of(swings: dict, i: int, tolerance: float = 0.0015) -> list[dict]:
    """Patterns visible as of bar i: a swing at position p is only confirmed
    once p + window <= i (it needs `window` bars after it to be a pivot)."""
    window = swings["window"]
    highs = [(ts, price) for (pos, ts, price) in swings["highs"] if pos + window <= i]
    lows = [(ts, price) for (pos, ts, price) in swings["lows"] if pos + window <= i]
    return _patterns_from_swings(highs, lows, tolerance)


def _cluster_levels(points: list[tuple], tolerance: float) -> list[dict]:
    """Group nearby swing levels into zones. `points` is [(ts, price), ...].
    Returns zones sorted by strength (how many swings formed them)."""
    prices = sorted(p for _, p in points)
    clusters: list[list[float]] = []
    for price in prices:
        if clusters and abs(price - clusters[-1][-1]) / clusters[-1][-1] <= tolerance:
            clusters[-1].append(price)
        else:
            clusters.append([price])
    zones = [{"price": round(sum(c) / len(c), 5), "strength": len(c)} for c in clusters]
    zones.sort(key=lambda z: z["strength"], reverse=True)
    return zones


def support_resistance_levels(df: pd.DataFrame, window: int = 3, tolerance: float = 0.0025) -> dict:
    """All support (swing-low) and resistance (swing-high) zones across the
    whole graph, clustered and ranked by strength."""
    swung = find_swing_points(df, window=window)
    highs = [(str(r["ts"]), float(r["high"])) for _, r in swung[swung["swing_high"]].iterrows()]
    lows = [(str(r["ts"]), float(r["low"])) for _, r in swung[swung["swing_low"]].iterrows()]
    return {
        "resistances": _cluster_levels(highs, tolerance),
        "supports": _cluster_levels(lows, tolerance),
    }


def detect_all_patterns(df: pd.DataFrame, window: int = 3, tolerance: float = 0.0015, max_each: int = 5) -> list[dict]:
    """Scan the ENTIRE graph (not just the latest swings) for every double
    top / double bottom, plus the strongest support/resistance zones. Used for
    the on-demand 'analyze the whole chart' view."""
    if len(df) < window * 4:
        return []

    swung = find_swing_points(df, window=window)
    highs = [(str(r["ts"]), float(r["high"])) for _, r in swung[swung["swing_high"]].iterrows()]
    lows = [(str(r["ts"]), float(r["low"])) for _, r in swung[swung["swing_low"]].iterrows()]

    detected: list[dict] = []

    # Every adjacent same-level swing-high pair = a double top across the graph.
    double_tops = []
    for a, b in zip(highs, highs[1:]):
        if abs(a[1] - b[1]) / a[1] <= tolerance:
            double_tops.append(
                {"pattern": "double_top", "direction": "bearish", "points": [
                    {"ts": a[0], "price": a[1]}, {"ts": b[0], "price": b[1]}]}
            )
    double_bottoms = []
    for a, b in zip(lows, lows[1:]):
        if abs(a[1] - b[1]) / a[1] <= tolerance:
            double_bottoms.append(
                {"pattern": "double_bottom", "direction": "bullish", "points": [
                    {"ts": a[0], "price": a[1]}, {"ts": b[0], "price": b[1]}]}
            )

    detected.extend(double_tops[-max_each:])
    detected.extend(double_bottoms[-max_each:])

    sr = support_resistance_levels(df, window=window, tolerance=2 * tolerance)
    for zone in sr["resistances"][:3]:
        detected.append({"pattern": "resistance_level", "direction": "neutral",
                         "strength": zone["strength"], "points": [{"ts": "", "price": zone["price"]}]})
    for zone in sr["supports"][:3]:
        detected.append({"pattern": "support_level", "direction": "neutral",
                         "strength": zone["strength"], "points": [{"ts": "", "price": zone["price"]}]})

    return detected


def detect_trend(df: pd.DataFrame, window: int = 3) -> str:
    """Whole-graph trend from swing structure: higher-highs + higher-lows is an
    uptrend, lower-highs + lower-lows a downtrend, otherwise sideways."""
    swung = find_swing_points(df, window=window)
    highs = [float(r["high"]) for _, r in swung[swung["swing_high"]].iterrows()]
    lows = [float(r["low"]) for _, r in swung[swung["swing_low"]].iterrows()]
    if len(highs) < 2 or len(lows) < 2:
        return "sideways"
    higher_highs = highs[-1] > highs[-2]
    higher_lows = lows[-1] > lows[-2]
    if higher_highs and higher_lows:
        return "uptrend"
    if not higher_highs and not higher_lows:
        return "downtrend"
    return "sideways"
