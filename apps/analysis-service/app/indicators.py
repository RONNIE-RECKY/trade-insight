"""Technical indicators computed on a candle DataFrame via pandas-ta."""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out["rsi_14"] = ta.rsi(out["close"], length=14)

    macd = ta.macd(out["close"])
    if macd is not None:
        out["macd"] = macd["MACD_12_26_9"]
        out["macd_signal"] = macd["MACDs_12_26_9"]
        out["macd_hist"] = macd["MACDh_12_26_9"]

    out["ema_20"] = ta.ema(out["close"], length=20)
    out["ema_50"] = ta.ema(out["close"], length=50)

    bbands = ta.bbands(out["close"], length=20)
    if bbands is not None:
        out["bb_lower"] = bbands["BBL_20_2.0_2.0"]
        out["bb_mid"] = bbands["BBM_20_2.0_2.0"]
        out["bb_upper"] = bbands["BBU_20_2.0_2.0"]

    out["atr_14"] = ta.atr(out["high"], out["low"], out["close"], length=14)

    stoch = ta.stoch(out["high"], out["low"], out["close"])
    if stoch is not None:
        cols = list(stoch.columns)
        out["stoch_k"] = stoch[cols[0]]
        out["stoch_d"] = stoch[cols[1]] if len(cols) > 1 else stoch[cols[0]]

    return out


def latest_indicator_signals(df: pd.DataFrame) -> dict:
    """Read the most recent row of an indicator-enriched DataFrame into a
    transparent dict of triggered conditions, for confluence scoring."""
    if df.empty or len(df) < 2:
        return {}

    return _signals_from_rows(df.iloc[-1], df.iloc[-2])


def indicator_signals_at(enriched: pd.DataFrame, i: int) -> dict:
    """Same as latest_indicator_signals but reads a precomputed enriched frame
    at bar `i` (using rows i and i-1) — avoids recomputing indicators per bar
    during a backtest walk."""
    if i < 1 or i >= len(enriched):
        return {}
    return _signals_from_rows(enriched.iloc[i], enriched.iloc[i - 1])


def _signals_from_rows(last, prev) -> dict:
    signals: dict[str, bool | float] = {}

    if pd.notna(last.get("rsi_14")):
        signals["rsi_14"] = round(float(last["rsi_14"]), 2)
        signals["rsi_oversold"] = bool(last["rsi_14"] < 30)
        signals["rsi_overbought"] = bool(last["rsi_14"] > 70)

    if pd.notna(last.get("macd")) and pd.notna(last.get("macd_signal")):
        signals["macd_bullish_cross"] = bool(
            prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]
        )
        signals["macd_bearish_cross"] = bool(
            prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]
        )

    if pd.notna(last.get("ema_20")) and pd.notna(last.get("ema_50")):
        signals["ema_bullish_cross"] = bool(
            prev["ema_20"] <= prev["ema_50"] and last["ema_20"] > last["ema_50"]
        )
        signals["ema_bearish_cross"] = bool(
            prev["ema_20"] >= prev["ema_50"] and last["ema_20"] < last["ema_50"]
        )

    if pd.notna(last.get("bb_lower")) and pd.notna(last.get("bb_upper")):
        signals["price_below_lower_band"] = bool(last["close"] < last["bb_lower"])
        signals["price_above_upper_band"] = bool(last["close"] > last["bb_upper"])

    # raw values + extra indicators used by the multi-strategy engine
    signals["close"] = float(last["close"])
    if pd.notna(last.get("ema_20")):
        signals["ema_20"] = float(last["ema_20"])
    if pd.notna(last.get("ema_50")):
        signals["ema_50"] = float(last["ema_50"])
    if pd.notna(last.get("macd_hist")):
        signals["macd_hist"] = float(last["macd_hist"])
    if pd.notna(last.get("stoch_k")):
        signals["stoch_k"] = round(float(last["stoch_k"]), 2)
        signals["stoch_oversold"] = bool(last["stoch_k"] < 20)
        signals["stoch_overbought"] = bool(last["stoch_k"] > 80)

    return signals
