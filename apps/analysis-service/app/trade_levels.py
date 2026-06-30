"""Compute concrete trade levels — entry, stop loss, take profit — from the
same evidence already used for the signal. These are rule-based and fully
explainable:

- entry  = latest close (the price the setup is read from)
- stop   = ATR-based protective stop on the opposite side, tightened to the
           nearest detected swing level when one sits between entry and the
           ATR stop (so the stop hugs real structure, not an arbitrary number)
- target = entry projected by `reward_multiple` x the risk distance, so the
           take-profit is always a stated multiple of the risk being taken —
           never a fabricated "guaranteed" target. The multiple itself scales
           with how much evidence backs the setup (confluence_score): a
           single-factor setup gets a conservative 1:2, a setup with most
           strategies agreeing earns a more ambitious 1:3 — more strategies
           agreeing means the structure backing the target is itself more
           confirmed, not that we're inflating the number for show.

Nothing here predicts that a trade will win. It only states, transparently,
where a disciplined entry/stop/target would sit for the detected direction.
"""
from __future__ import annotations

# A 1.5x-ATR stop was unnecessarily wide for how tightly these setups are
# defined elsewhere (ATR already measures the instrument's real recent
# volatility) — tightened to 0.9x so the stop sits close to invalidation
# without being so tight (0.5x) that ordinary noise clips it constantly.
ATR_STOP_MULTIPLE = 0.9
MIN_REWARD_MULTIPLE = 2.0   # worst case: still a 1:2 risk:reward
MAX_REWARD_MULTIPLE = 3.0   # best case (strong confluence): 1:3
DEFAULT_REWARD_MULTIPLE = MIN_REWARD_MULTIPLE


def _reward_multiple_for(confluence_score: int | None) -> float:
    if confluence_score is None:
        return DEFAULT_REWARD_MULTIPLE
    if confluence_score >= 5:
        return MAX_REWARD_MULTIPLE
    if confluence_score >= 3:
        return 2.5
    return MIN_REWARD_MULTIPLE


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
    confluence_score: int | None = None,
    reward_multiple: float | None = None,
) -> dict | None:
    if direction not in ("bullish", "bearish") or not atr or atr <= 0:
        return None

    if reward_multiple is None:
        reward_multiple = _reward_multiple_for(confluence_score)

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
