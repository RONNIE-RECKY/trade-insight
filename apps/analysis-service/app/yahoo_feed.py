"""Keyless live market data via Yahoo Finance's public chart API.

This gives real OHLC candles for forex, gold and crypto without any API key,
so charts and prices are accurate out of the box. Twelve Data (with a key)
still takes priority when configured; this is the no-setup default, and the
deterministic fixtures remain the final fallback if the network is unavailable.
"""
from __future__ import annotations

import httpx
import pandas as pd

_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TradeInsight/1.0)"}

# Our symbol -> Yahoo symbol. Gold spot (XAUUSD=X) is delisted on Yahoo, so we
# use the gold futures front month (GC=F), which tracks spot closely.
_YAHOO_SYMBOL = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",
    "XAUUSD": "GC=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
}

# our interval -> (yahoo interval, yahoo range, resample target or None)
_INTERVAL = {
    "5min": ("5m", "1mo", None),
    "15min": ("15m", "1mo", None),
    "30min": ("30m", "1mo", None),
    "1h": ("60m", "3mo", None),
    "4h": ("60m", "2y", "4h"),  # Yahoo has no 4h; resample from hourly
    "1day": ("1d", "2y", None),
}


def supports(symbol: str) -> bool:
    return symbol in _YAHOO_SYMBOL


def fetch_yahoo_candles(symbol: str, interval: str = "1day", count: int = 300) -> list[dict]:
    if symbol not in _YAHOO_SYMBOL:
        raise ValueError(f"no Yahoo mapping for {symbol}")
    y_symbol = _YAHOO_SYMBOL[symbol]
    y_interval, y_range, resample = _INTERVAL.get(interval, ("1d", "2y", None))

    resp = httpx.get(
        f"{_YAHOO_BASE}{y_symbol}",
        params={"interval": y_interval, "range": y_range},
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()

    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise RuntimeError(f"Yahoo error for {symbol}: {chart.get('error')}")

    result = chart["result"][0]
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]
    opens, highs = quote.get("open", []), quote.get("high", [])
    lows, closes = quote.get("low", []), quote.get("close", [])
    volumes = quote.get("volume", [])

    rows = []
    for i, ts in enumerate(timestamps):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if None in (o, h, l, c):
            continue
        rows.append(
            {
                "ts": pd.to_datetime(ts, unit="s", utc=True),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0.0,
            }
        )

    if not rows:
        raise RuntimeError(f"Yahoo returned no usable candles for {symbol}")

    df = pd.DataFrame(rows)

    if resample == "4h":
        df = _resample(df, "4h")

    df = df.tail(count)
    df["ts"] = df["ts"].astype(str)
    return df.to_dict(orient="records")


def fetch_yahoo_quote(symbol: str) -> dict:
    """Latest traded price + its timestamp, independent of candle granularity.

    Candle endpoints only update once a bar closes (e.g. up to 5 minutes
    stale on the 5min timeframe); this hits the same chart API with a tight
    1-minute/1-day window and reads `meta.regularMarketPrice`, which Yahoo
    updates close to real-time for FX/crypto/futures.
    """
    if symbol not in _YAHOO_SYMBOL:
        raise ValueError(f"no Yahoo mapping for {symbol}")
    y_symbol = _YAHOO_SYMBOL[symbol]

    resp = httpx.get(
        f"{_YAHOO_BASE}{y_symbol}",
        params={"interval": "1m", "range": "1d"},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()

    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise RuntimeError(f"Yahoo error for {symbol}: {chart.get('error')}")

    meta = chart["result"][0].get("meta", {})
    price = meta.get("regularMarketPrice")
    ts = meta.get("regularMarketTime")
    if price is None or ts is None:
        raise RuntimeError(f"Yahoo quote missing price/time for {symbol}")
    return {"price": float(price), "ts": pd.to_datetime(ts, unit="s", utc=True).isoformat()}


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    s = df.set_index("ts")
    agg = s.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open", "high", "low", "close"])
    return agg.reset_index()
