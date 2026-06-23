"""Deterministic fixture OHLC candles, used when no TWELVE_DATA_API_KEY is configured.

Generates a seeded random-walk price series per symbol so behavior is
reproducible across runs during development.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "XAUUSD",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "BTCUSD",
    "ETHUSD",
]

# Approximate, plausible 2026 price levels. These are SIMULATED reference points
# for the fixture random-walk — real values arrive once TWELVE_DATA_API_KEY is set.
_BASE_PRICE = {
    "EURUSD": 1.0820,
    "GBPUSD": 1.2880,
    "USDJPY": 152.40,
    "XAUUSD": 3350.0,
    "USDCHF": 0.8850,
    "AUDUSD": 0.6720,
    "USDCAD": 1.3650,
    "NZDUSD": 0.6150,
    "BTCUSD": 96000.0,
    "ETHUSD": 3650.0,
}

_STEP_PCT = {
    "EURUSD": 0.0008,
    "GBPUSD": 0.0008,
    "USDJPY": 0.0008,
    "XAUUSD": 0.0012,
    "USDCHF": 0.0008,
    "AUDUSD": 0.0009,
    "USDCAD": 0.0008,
    "NZDUSD": 0.0009,
    "BTC/USD": 0.015,
    "ETH/USD": 0.015,
}


def generate_candles(symbol: str, interval: str = "1day", count: int = 300) -> list[dict]:
    if symbol not in _BASE_PRICE:
        raise ValueError(f"unknown fixture symbol: {symbol}")

    rng = random.Random(f"{symbol}:{interval}:{count}")
    price = _BASE_PRICE[symbol]
    step_pct = _STEP_PCT[symbol]

    interval_delta = {
        "5min": timedelta(minutes=5),
        "15min": timedelta(minutes=15),
        "30min": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1day": timedelta(days=1),
    }.get(interval, timedelta(days=1))

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if interval_delta >= timedelta(hours=1):
        now = now.replace(minute=0)
    else:
        # snap to the interval boundary (e.g. nearest 5/15/30 min)
        step_minutes = int(interval_delta.total_seconds() // 60)
        now = now.replace(minute=(now.minute // step_minutes) * step_minutes)
    if interval_delta >= timedelta(days=1):
        now = now.replace(hour=0)
    candles = []
    for i in range(count):
        ts = now - interval_delta * (count - i)
        drift = rng.gauss(0, step_pct)
        open_p = price
        close_p = price * (1 + drift)
        high_p = max(open_p, close_p) * (1 + abs(rng.gauss(0, step_pct / 2)))
        low_p = min(open_p, close_p) * (1 - abs(rng.gauss(0, step_pct / 2)))
        volume = rng.uniform(1000, 5000)
        candles.append(
            {
                "ts": ts.isoformat(),
                "open": round(open_p, 5),
                "high": round(high_p, 5),
                "low": round(low_p, 5),
                "close": round(close_p, 5),
                "volume": round(volume, 2),
            }
        )
        price = close_p

    return candles
