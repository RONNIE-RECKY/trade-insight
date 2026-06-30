"""Candle ingestion: Twelve Data when TWELVE_DATA_API_KEY is set, fixture data otherwise.

Either way, results are cached in the `candles` table so we only re-fetch
deltas since the last stored timestamp.
"""
from __future__ import annotations

import os

import httpx
import pandas as pd

from . import fixtures
from .db import db_session

TWELVE_DATA_BASE_URL = "https://api.twelvedata.com/time_series"

_INTERVAL_MAP = {
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "1h": "1h",
    "4h": "4h",
    "1day": "1day",
}


def _api_key() -> str | None:
    return os.environ.get("TWELVE_DATA_API_KEY")


def fetch_live_candles(symbol: str, interval: str = "1day", outputsize: int = 300) -> list[dict]:
    key = _api_key()
    if not key:
        raise RuntimeError("TWELVE_DATA_API_KEY not set")

    params = {
        "symbol": symbol,
        "interval": _INTERVAL_MAP.get(interval, interval),
        "outputsize": outputsize,
        "apikey": key,
        "format": "JSON",
    }
    resp = httpx.get(TWELVE_DATA_BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") == "error":
        raise RuntimeError(f"Twelve Data error: {payload.get('message')}")

    values = payload.get("values", [])
    candles = []
    for v in reversed(values):  # API returns newest first
        candles.append(
            {
                "ts": v["datetime"],
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
                "volume": float(v.get("volume") or 0),
            }
        )
    return candles


def fetch_live_quote(symbol: str) -> dict:
    key = _api_key()
    if not key:
        raise RuntimeError("TWELVE_DATA_API_KEY not set")
    resp = httpx.get(
        "https://api.twelvedata.com/price",
        params={"symbol": symbol, "apikey": key},
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "price" not in payload:
        raise RuntimeError(f"Twelve Data quote error: {payload.get('message', payload)}")
    import datetime as _dt

    return {"price": float(payload["price"]), "ts": _dt.datetime.now(_dt.timezone.utc).isoformat()}


def get_live_price(symbol: str) -> dict:
    """Latest traded price independent of candle granularity (see yahoo_feed.fetch_yahoo_quote
    for why candles alone can be several minutes behind the exact-moment price)."""
    if _api_key():
        try:
            return {**fetch_live_quote(symbol), "source": "live"}
        except Exception:
            pass
    try:
        from . import yahoo_feed

        if yahoo_feed.supports(symbol):
            return {**yahoo_feed.fetch_yahoo_quote(symbol), "source": "live"}
    except Exception:
        pass

    last = fixtures.generate_candles(symbol, "1day", 1)
    if not last:
        raise RuntimeError(f"no price available for {symbol}")
    return {"price": last[-1]["close"], "ts": last[-1]["ts"], "source": "simulated"}


_LAST_SOURCE = "unknown"


def _fetch_candles(symbol: str, interval: str, count: int) -> tuple[list[dict], str]:
    """Source priority: Twelve Data (if key) -> Yahoo (keyless live) -> fixtures."""
    if _api_key():
        try:
            return fetch_live_candles(symbol, interval, count), "live"
        except Exception:
            pass
    try:
        from . import yahoo_feed

        if yahoo_feed.supports(symbol):
            return yahoo_feed.fetch_yahoo_candles(symbol, interval, count), "live"
    except Exception:
        pass
    return fixtures.generate_candles(symbol, interval, count), "simulated"


def get_candles(symbol: str, interval: str = "1day", count: int = 300, refresh: bool = True) -> pd.DataFrame:
    """Return cached candles for symbol/interval, fetching+caching new ones first if possible."""
    global _LAST_SOURCE
    if refresh:
        new_candles, source = _fetch_candles(symbol, interval, count)
        _LAST_SOURCE = source
        _store_candles(symbol, interval, new_candles)

    with db_session() as conn:
        rows = conn.execute(
            "SELECT ts, open, high, low, close, volume FROM candles "
            "WHERE symbol = ? AND interval = ? ORDER BY ts DESC LIMIT ?",
            (symbol, interval, count),
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame([dict(r) for r in rows]).iloc[::-1].reset_index(drop=True)
    # stored ts can mix formats (fixtures use ISO 'T', Yahoo uses space) — parse per-element
    df["ts"] = pd.to_datetime(df["ts"], format="mixed", utc=True)
    return df


def data_source() -> str:
    """Best-effort report of where candles are currently coming from."""
    if _api_key():
        return "live"
    if _LAST_SOURCE != "unknown":
        return _LAST_SOURCE
    try:
        from . import yahoo_feed

        yahoo_feed.fetch_yahoo_candles("EURUSD", "1day", 2)
        return "live"
    except Exception:
        return "simulated"


def _store_candles(symbol: str, interval: str, candles: list[dict]) -> None:
    with db_session() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO candles (symbol, interval, ts, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (symbol, interval, c["ts"], c["open"], c["high"], c["low"], c["close"], c["volume"])
                for c in candles
            ],
        )
