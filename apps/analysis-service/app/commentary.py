"""Template-based natural-language commentary, generated strictly from the
already-computed factors (indicators, patterns, timeframe agreement, news
sentiment) — not a separate model call. This keeps the "AI analyst" voice
honest: it can only describe evidence that's actually in the data, since it's
assembled from the same structured fields the UI renders elsewhere.
"""
from __future__ import annotations

_TIMEFRAME_LABELS = {
    "5min": "5-minute",
    "15min": "15-minute",
    "30min": "30-minute",
    "1h": "1-hour",
    "4h": "4-hour",
    "1day": "daily",
}


def generate_analysis_commentary(
    symbol: str,
    interval: str,
    direction: str,
    factors: list[str],
    position: dict,
    news_result: dict | None = None,
) -> str:
    """Commentary for a single chosen-timeframe analysis (the 'bot analyzes the
    chart' view). Describes the selected timeframe's setup, the prevailing trend
    and where price sits — all from the already-computed data."""
    tf_label = _TIMEFRAME_LABELS.get(interval, interval)
    trend = position.get("trend", "sideways")
    range_pos = position.get("range_position_pct")

    if direction == "neutral":
        lead = f"On the {tf_label} chart, {symbol} has no clean directional setup right now"
    else:
        factor_text = ", ".join(f.replace("_", " ") for f in factors) or "the latest momentum read"
        lead = f"On the {tf_label} chart, {symbol} is leaning {direction}, driven by {factor_text}"

    parts = [lead + f". The broader structure is a {trend}"]

    if range_pos is not None:
        if range_pos >= 75:
            parts.append(f", with price near the top of its recent range ({range_pos}%)")
        elif range_pos <= 25:
            parts.append(f", with price near the bottom of its recent range ({range_pos}%)")
        else:
            parts.append(f", with price mid-range ({range_pos}%)")

    nearest_sup = position.get("nearest_support")
    nearest_res = position.get("nearest_resistance")
    if nearest_sup is not None or nearest_res is not None:
        bits = []
        if nearest_sup is not None:
            bits.append(f"support around {nearest_sup}")
        if nearest_res is not None:
            bits.append(f"resistance around {nearest_res}")
        parts.append(". Watch " + " and ".join(bits))

    sentence = "".join(parts) + "."

    if news_result and news_result.get("headlines"):
        ns = news_result["sentiment"]
        if direction != "neutral" and ns == direction:
            sentence += f" Recent headlines also lean {ns}, reinforcing the bias."
        elif direction != "neutral" and ns not in ("neutral", direction):
            sentence += f" Note: headlines lean {ns}, against this setup — treat with caution."

    return sentence


def generate_commentary(symbol: str, mtf_result: dict, news_result: dict | None = None) -> str:
    direction = mtf_result["direction"]
    agreeing = [tf for tf, r in mtf_result["timeframes"].items() if r["direction"] == direction]
    agreeing_labels = [_TIMEFRAME_LABELS.get(tf, tf) for tf in agreeing]

    if direction == "neutral" or not agreeing:
        return f"{symbol} shows no clear directional confluence across timeframes right now — sitting this one out."

    factors = set()
    for tf in agreeing:
        factors.update(mtf_result["timeframes"][tf]["factors"])
    factor_text = ", ".join(f.replace("_", " ") for f in sorted(factors)) or "no single standout factor"

    sentence = (
        f"{symbol} is showing {direction} confluence across the {', '.join(agreeing_labels)} "
        f"timeframe{'s' if len(agreeing_labels) > 1 else ''}, driven by {factor_text}."
    )

    if news_result and news_result.get("headlines"):
        news_sentiment = news_result["sentiment"]
        if news_sentiment == direction:
            sentence += f" Recent headlines also lean {news_sentiment}, reinforcing the case."
        elif news_sentiment == "neutral":
            sentence += " Recent headlines are mixed/neutral, so this leans purely on the technical picture."
        else:
            sentence += (
                f" Note: recent headlines actually lean {news_sentiment}, which contradicts this technical setup —"
                " treat with extra caution."
            )

    return sentence
