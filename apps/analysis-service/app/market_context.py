"""Where price currently sits within the whole-graph structure — the
'current position' read. Pure description of the present state (range
location, EMA relationship, nearest support/resistance, distance to the
proposed trade levels). Nothing here predicts the future."""
from __future__ import annotations

import pandas as pd

from .patterns import detect_trend, support_resistance_levels


def current_position(df: pd.DataFrame, enriched: pd.DataFrame, levels: dict | None = None) -> dict:
    if df.empty:
        return {}

    last = enriched.iloc[-1]
    price = float(last["close"])

    period_high = float(df["high"].max())
    period_low = float(df["low"].min())
    rng = period_high - period_low
    range_position_pct = round((price - period_low) / rng * 100, 1) if rng > 0 else None

    ema_20 = float(last["ema_20"]) if pd.notna(last.get("ema_20")) else None
    ema_50 = float(last["ema_50"]) if pd.notna(last.get("ema_50")) else None

    sr = support_resistance_levels(df)
    resistances_above = sorted([z["price"] for z in sr["resistances"] if z["price"] > price])
    supports_below = sorted([z["price"] for z in sr["supports"] if z["price"] < price], reverse=True)
    nearest_resistance = resistances_above[0] if resistances_above else None
    nearest_support = supports_below[0] if supports_below else None

    context = {
        "current_price": round(price, 5),
        "period_high": round(period_high, 5),
        "period_low": round(period_low, 5),
        "range_position_pct": range_position_pct,
        "trend": detect_trend(df),
        "above_ema_20": (price > ema_20) if ema_20 is not None else None,
        "above_ema_50": (price > ema_50) if ema_50 is not None else None,
        "ema_20": round(ema_20, 5) if ema_20 is not None else None,
        "ema_50": round(ema_50, 5) if ema_50 is not None else None,
        "nearest_support": round(nearest_support, 5) if nearest_support is not None else None,
        "nearest_resistance": round(nearest_resistance, 5) if nearest_resistance is not None else None,
    }

    if levels:
        context["distance_to_entry_pct"] = _pct(price, levels["entry"])
        context["distance_to_stop_pct"] = _pct(price, levels["stop_loss"])
        context["distance_to_target_pct"] = _pct(price, levels["take_profit"])

    return context


def _pct(price: float, level: float) -> float:
    if price == 0:
        return 0.0
    return round((level - price) / price * 100, 2)
