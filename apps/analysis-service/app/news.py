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
from datetime import datetime, timedelta, timezone

import httpx

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"

_CURRENCY_KEYWORDS = {
    "USD": ["dollar", "fed", "federal reserve", "us economy", "treasury", "powell"],
    "EUR": ["euro", "ecb", "eurozone", "lagarde"],
    "GBP": ["pound", "sterling", "bank of england", "boe"],
    "JPY": ["yen", "boj", "bank of japan"],
    "CHF": ["franc", "snb", "swiss national bank"],
    "AUD": ["aussie", "rba", "reserve bank of australia"],
    "CAD": ["loonie", "boc", "bank of canada"],
    "NZD": ["kiwi", "rbnz"],
    "XAU": ["gold", "bullion", "safe haven", "xau"],
    "BTC": ["bitcoin", "btc", "crypto"],
    "ETH": ["ethereum", "ether", "eth"],
}

_POSITIVE_WORDS = ["rallies", "rises", "strengthens", "surges", "beats expectations", "optimistic", "rate hike", "growth", "upbeat"]
_NEGATIVE_WORDS = ["falls", "weakens", "drops", "slumps", "misses expectations", "pessimistic", "rate cut", "recession", "downbeat"]

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


def _score_headline(headline: str) -> int:
    text = headline.lower()
    score = 0
    for word in _POSITIVE_WORDS:
        if word in text:
            score += 1
    for word in _NEGATIVE_WORDS:
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


def get_news_sentiment(symbol: str) -> dict:
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
        matched_base = any(kw in text for kw in base_keywords)
        matched_quote = any(kw in text for kw in quote_keywords)
        if not matched_base and not matched_quote:
            continue
        score = _score_headline(headline)
        # quote-currency news affects the pair inversely to base-currency news
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
    }
