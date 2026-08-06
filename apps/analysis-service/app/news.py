"""Forex/market news sentiment: Finnhub when FINNHUB_API_KEY is set,
deterministic fixture headlines otherwise — same fallback pattern as
data_feed.py for candles.

Sentiment is derived by counting positive/negative keywords in recent
headlines relevant to the symbol's currencies. This is a simple, auditable
heuristic, not a black-box model — every contributing headline is returned
alongside the verdict so the reasoning stays transparent.
"""
from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

# 5-minute process-level cache — avoids hitting Finnhub on every chart
# auto-refresh (which runs as often as every 15 s on 5M timeframe).
_NEWS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_NEWS_TTL = 300  # seconds

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"

_CURRENCY_KEYWORDS = {
    "USD": ["dollar", "greenback", "fed", "federal reserve", "us economy", "treasury", "powell"],
    "EUR": ["euro", "ecb", "eurozone", "lagarde"],
    "GBP": ["pound", "sterling", "bank of england", "boe"],
    "JPY": ["yen", "boj", "bank of japan"],
    "CHF": ["franc", "snb", "swiss national bank"],
    "AUD": ["aussie", "australian dollar", "rba", "reserve bank of australia"],
    "CAD": ["loonie", "canadian dollar", "boc", "bank of canada"],
    "NZD": ["kiwi", "new zealand dollar", "rbnz"],
    "XAU": ["gold", "bullion", "safe haven", "xau"],
    "BTC": ["bitcoin", "btc", "crypto"],
    "ETH": ["ethereum", "ether", "eth"],
}

# "dollar" alone is ambiguous — an "Aussie dollar rises" headline was matching
# USD and flipping unrelated pairs' sentiment. Other currencies' dollar phrases
# are stripped before USD keywords are tested, so only the US dollar counts.
_FOREIGN_DOLLARS = (
    "aussie dollar",
    "australian dollar",
    "canadian dollar",
    "new zealand dollar",
    "nz dollar",
    "kiwi dollar",
    "singapore dollar",
    "hong kong dollar",
    "taiwan dollar",
)


def _mask_foreign_dollars(text: str) -> str:
    """Blank out non-US 'dollar' mentions so USD matching can't claim them."""
    for phrase in _FOREIGN_DOLLARS:
        text = text.replace(phrase, "")
    return text

# Sentiment lexicon: price-action words plus the FUNDAMENTALS vocabulary that
# actually moves FX/gold — central-bank stance (hawkish/dovish, hiking/easing),
# inflation and labour-market surprises, yields and risk appetite. Scoring is
# from the CURRENCY's perspective (hawkish/strong data = currency-positive);
# get_news_sentiment then inverts quote-currency scores for the pair, so e.g.
# a hawkish-Fed headline is USD-positive and therefore bearish for XAUUSD.
_POSITIVE_WORDS = [
    # price action
    "rallies", "rises", "strengthens", "surges", "climbs", "jumps", "rebounds", "upbeat",
    # central-bank stance / policy
    "rate hike", "raises rates", "hawkish", "tightening", "higher for longer",
    # data surprises / economy
    "beats expectations", "better than expected", "strong jobs", "jobs beat",
    "growth", "expansion", "optimistic", "resilient", "hot inflation", "inflation rises",
    "yields rise", "yields climb",
]
_NEGATIVE_WORDS = [
    # price action
    "falls", "weakens", "drops", "slumps", "tumbles", "slides", "plunges", "downbeat",
    # central-bank stance / policy
    "rate cut", "cuts rates", "dovish", "easing", "pause in tightening", "pivot",
    # data surprises / economy
    "misses expectations", "worse than expected", "weak jobs", "jobs miss",
    "recession", "contraction", "pessimistic", "slowdown", "inflation cools",
    "inflation eases", "yields fall", "yields drop",
]
# Gold-only extras: gold is a safe-haven, so risk-off language is bullish for
# XAU even though it isn't "positive" for any currency. Applied only to
# headlines matched on the XAU side.
_GOLD_BULLISH_WORDS = [
    "safe haven", "risk-off", "geopolitical tension", "uncertainty", "flight to safety",
    "dollar weakens", "central bank buying", "haven demand",
]
_GOLD_BEARISH_WORDS = ["risk-on", "risk appetite", "dollar strengthens", "profit-taking in gold"]

_FIXTURE_HEADLINES = [
    "Dollar strengthens as Fed signals rate hike path stays on track",
    "Euro weakens after ECB hints at further easing amid sluggish growth",
    "Gold rallies as investors seek safe haven amid geopolitical tension",
    "Pound falls on weak UK retail sales data",
    "Yen slumps to multi-month low as BOJ holds rates steady",
    "Aussie dollar rises on upbeat Australian employment figures",
    "Loonie weakens as oil prices drop on demand concerns",
    "Swiss franc steady ahead of SNB policy meeting",
    "Kiwi dollar dips after RBNZ signals pause in tightening cycle",
    "US economy beats expectations with strong jobs report",
]


def _symbol_currencies(symbol: str) -> list[str]:
    s = symbol.replace("/", "").upper()
    if s.startswith("XAU"):
        return ["XAU", "USD"]
    if len(s) == 6:
        return [s[:3], s[3:]]
    return []


def _score_headline(headline: str, gold: bool = False) -> int:
    text = headline.lower()
    score = 0
    for word in _POSITIVE_WORDS:
        if word in text:
            score += 1
    for word in _NEGATIVE_WORDS:
        if word in text:
            score -= 1
    if gold:  # safe-haven / risk-appetite vocabulary only applies to XAU
        for word in _GOLD_BULLISH_WORDS:
            if word in text:
                score += 1
        for word in _GOLD_BEARISH_WORDS:
            if word in text:
                score -= 1
    return score


def _fetch_live_headlines() -> list[str]:
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        raise RuntimeError("FINNHUB_API_KEY not set")

    to_date = datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=2)
    params = {"category": "forex", "token": key}
    resp = httpx.get(FINNHUB_NEWS_URL, params=params, timeout=15)
    resp.raise_for_status()
    items = resp.json()
    return [item.get("headline", "") for item in items if item.get("headline")][:50]


def _fixture_headlines(symbol: str) -> list[str]:
    rng = random.Random(f"news:{symbol}:{datetime.now(timezone.utc).date().isoformat()}")
    return rng.sample(_FIXTURE_HEADLINES, k=min(5, len(_FIXTURE_HEADLINES)))


def _fetch_sentiment(symbol: str) -> dict:
    try:
        headlines = _fetch_live_headlines()
        source = "live"
    except Exception:
        headlines = _fixture_headlines(symbol)
        source = "fixture"

    currencies = _symbol_currencies(symbol)  # [base, quote] — base strengthening is bullish for the pair, quote strengthening is bearish
    base_keywords = _CURRENCY_KEYWORDS.get(currencies[0], []) if currencies else []
    quote_keywords = _CURRENCY_KEYWORDS.get(currencies[1], []) if len(currencies) > 1 else []

    relevant = []
    pair_score = 0
    for headline in headlines:
        text = headline.lower()
        # USD matching runs against text with foreign "dollar" phrases removed
        base_text = _mask_foreign_dollars(text) if currencies and currencies[0] == "USD" else text
        quote_text = _mask_foreign_dollars(text) if len(currencies) > 1 and currencies[1] == "USD" else text
        matched_base = any(kw in base_text for kw in base_keywords)
        matched_quote = any(kw in quote_text for kw in quote_keywords)
        if not matched_base and not matched_quote:
            continue
        gold_side = matched_base and currencies and currencies[0] == "XAU"
        score = _score_headline(headline, gold=gold_side)
        pair_contribution = score if matched_base else -score
        relevant.append({"headline": headline, "score": score, "currency_side": "base" if matched_base else "quote"})
        pair_score += pair_contribution

    if pair_score > 0:
        sentiment = "bullish"
    elif pair_score < 0:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "symbol": symbol,
        "source": source,
        "sentiment": sentiment,
        "score": pair_score,
        "headlines": relevant,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_news_sentiment(symbol: str) -> dict:
    """Return news sentiment for the symbol, using a 5-minute cache so
    callers (analysis, signal scan, chart refresh) don't hammer Finnhub."""
    cached_ts, cached = _NEWS_CACHE.get(symbol, (0.0, {}))
    if cached and time.monotonic() - cached_ts < _NEWS_TTL:
        return cached
    result = _fetch_sentiment(symbol)
    _NEWS_CACHE[symbol] = (time.monotonic(), result)
    return result
