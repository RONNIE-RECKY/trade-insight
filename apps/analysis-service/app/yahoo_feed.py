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

# our interval -> pandas floor frequency, used to snap Yahoo's in-progress bar
# onto its proper bar boundary (see fetch_yahoo_candles)
_PANDAS_FREQ = {
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "1h": "1h",
    "4h": "4h",
    "1day": "1D",
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


# Spot gold. Yahoo delisted XAUUSD=X, so candles come from the front-month
# future (GC=F) — but futures carry a basis (contango) over spot that has run
# $50-60 lately. Publishing futures levels under the label "XAUUSD" means our
# entry/stop/target don't exist on a trader's spot chart, so we anchor to a
# real spot quote and shift the futures candles onto spot levels.
_SPOT_GOLD_URL = "https://api.gold-api.com/price/XAU"


def fetch_spot_gold() -> float:
    """Current spot XAU/USD price (not futures). Raises if unavailable."""
    resp = httpx.get(_SPOT_GOLD_URL, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    price = resp.json().get("price")
    if price is None:
        raise RuntimeError("spot gold API returned no price")
    return float(price)


def _gold_basis(futures_last_close: float) -> float:
    """spot - futures. Applied to every OHLC value so the candle series sits on
    spot levels while keeping the futures series' real shape/volatility.
    Returns 0.0 if spot is unavailable — better an unshifted series than a
    silently wrong one."""
    try:
        return fetch_spot_gold() - futures_last_close
    except Exception as e:  # noqa: BLE001
        print(f"[yahoo_feed] spot gold unavailable, serving unadjusted futures: {e}", flush=True)
        return 0.0


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

    # Yahoo appends the IN-PROGRESS bar stamped with the current clock time
    # (e.g. 07:22:16 in an hourly series) rather than its bar boundary. Left
    # alone, every poll stores another row — flat O=H=L=C junk bars that skew
    # indicators, pattern detection and the backtest. Snap timestamps down to
    # the interval boundary so the forming bar keeps REPLACING itself in the
    # cache (same ts) instead of accumulating.
    # Yahoo returns BOTH the completed bar and the partial one, so after
    # flooring they collide — merge them as OHLC (open=first, high=max,
    # low=min, close=last) rather than letting the flat partial bar overwrite
    # the real bar's range.
    freq = _PANDAS_FREQ.get(interval)
    if freq and not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.floor(freq)
        if df["ts"].duplicated().any():
            df = (
                df.groupby("ts", as_index=False)
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .sort_values("ts")
            )

    df = df.tail(count)

    # Gold: shift the futures series onto spot levels (see _gold_basis).
    if symbol == "XAUUSD" and not df.empty:
        basis = _gold_basis(float(df["close"].iloc[-1]))
        if basis:
            for col in ("open", "high", "low", "close"):
                df[col] = df[col] + basis

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

    # Gold: quote real spot, not the front-month future it's charted from.
    if symbol == "XAUUSD":
        try:
            import datetime as _dt

            return {"price": fetch_spot_gold(), "ts": _dt.datetime.now(_dt.timezone.utc).isoformat()}
        except Exception as e:  # noqa: BLE001 — fall through to the futures quote
            print(f"[yahoo_feed] spot gold quote failed, using futures: {e}", flush=True)

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
