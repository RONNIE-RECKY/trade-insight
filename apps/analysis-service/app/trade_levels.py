"""Compute concrete trade levels — entry, stop loss, take profit — from the
same evidence already used for the signal. These are rule-based and fully
explainable:

- entry  = latest close (the price the setup is read from)
- stop   = ATR-based protective stop on the opposite side, tightened to the
           nearest detected swing level when one sits between entry and the
           ATR stop (so the stop hugs real structure, not an arbitrary number)
- target = entry projected by `reward_multiple` x the risk distance (fixed
           risk:reward), so the take-profit is always a stated multiple of the
           risk being taken — never a fabricated "guaranteed" target.

Nothing here predicts that a trade will win. It only states, transparently,
where a disciplined entry/stop/target would sit for the detected direction.
"""
from __future__ import annotations

ATR_STOP_MULTIPLE = 1.5
DEFAULT_REWARD_MULTIPLE = 2.0


def _nearest_level(patterns: list[dict], kind: str) -> float | None:
    for p in patterns:
        if p["pattern"] == kind and p["points"]:
            return float(p["points"][-1]["price"])
    return None


def compute_trade_levels(
    direction: str,
    entry: float,
    atr: float | None,
    patterns: list[dict],
    reward_multiple: float = DEFAULT_REWARD_MULTIPLE,
) -> dict | None:
    if direction not in ("bullish", "bearish") or not atr or atr <= 0:
        return None

    atr_distance = ATR_STOP_MULTIPLE * atr

    if direction == "bullish":
        stop = entry - atr_distance
        support = _nearest_level(patterns, "support_level")
        # if a support sits just under entry, tuck the stop a hair below it
        if support is not None and support < entry and support > stop:
            stop = support - 0.1 * atr
        risk = entry - stop
        target = entry + reward_multiple * risk
    else:  # bearish
        stop = entry + atr_distance
        resistance = _nearest_level(patterns, "resistance_level")
        if resistance is not None and resistance > entry and resistance < stop:
            stop = resistance + 0.1 * atr
        risk = stop - entry
        target = entry - reward_multiple * risk

    if risk <= 0:
        return None

    return {
        "entry": round(entry, 5),
        "stop_loss": round(stop, 5),
        "take_profit": round(target, 5),
        "risk": round(risk, 5),
        "risk_reward": round((abs(target - entry) / risk), 2),
    }
