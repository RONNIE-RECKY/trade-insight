"""Extract a candlestick series from an uploaded chart SCREENSHOT.

How it actually works (no black-box claims):
- We scan the image for pixels matching a bullish (green-ish) or bearish
  (red-ish) candle colour — the two colours essentially every charting tool
  uses (TradingView, MT4/5, etc).
- Pixel columns are grouped into candles by horizontal gaps.
- For each candle, the full coloured vertical extent gives the high/low; the
  body (the widest, most common columns in the group) gives the open/close.
- Direction (bullish/bearish) comes directly from which colour matched.

Honesty boundary: without OCR'ing the axis labels (which most screenshots
render too small/varied to read reliably), we cannot recover the chart's
real price scale. The extracted series is therefore in *relative* units.
Trend, momentum (RSI/MACD direction), and pattern detection are valid on
relative units (their math is scale-invariant under positive linear scaling),
but any entry/stop/target levels computed from this image are illustrative,
not real prices — the API response says so explicitly so the UI can warn
the user rather than implying false precision.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

# Loose RGB heuristics for the two standard candle colours.
def _is_bullish(r, g, b):
    return (g > r + 12) & (g > b + 5) & (g > 60)


def _is_bearish(r, g, b):
    return (r > g + 12) & (r > b * 0.6) & (r > 60)


def extract_candles_from_image(image_bytes: bytes, max_candles: int = 200) -> dict:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # downscale very large screenshots for speed; keep aspect ratio
    if img.width > 1600:
        ratio = 1600 / img.width
        img = img.resize((1600, int(img.height * ratio)))

    arr = np.asarray(img, dtype=np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    bull_mask = _is_bullish(r, g, b)
    bear_mask = _is_bearish(r, g, b)
    candle_mask = bull_mask | bear_mask

    col_has_candle = candle_mask.any(axis=0)
    if not col_has_candle.any():
        return {"candles": [], "note": "no candlestick colours detected in this image"}

    height = arr.shape[0]

    # group contiguous columns (with small gap tolerance) into candle clusters
    cols = np.where(col_has_candle)[0]
    groups: list[list[int]] = []
    current = [int(cols[0])]
    for x in cols[1:]:
        if x - current[-1] <= 2:  # tolerate 1-2px anti-aliasing gaps
            current.append(int(x))
        else:
            groups.append(current)
            current = [int(x)]
    groups.append(current)

    candles = []
    for group in groups:
        sub_bull = bull_mask[:, group]
        sub_bear = bear_mask[:, group]
        is_bull = sub_bull.sum() >= sub_bear.sum()
        sub = sub_bull if is_bull else sub_bear

        col_tops, col_bottoms, col_widths = [], [], []
        for ci in range(sub.shape[1]):
            ys = np.where(sub[:, ci])[0]
            if ys.size == 0:
                continue
            col_tops.append(int(ys.min()))
            col_bottoms.append(int(ys.max()))

        if not col_tops:
            continue

        high_y = min(col_tops)       # topmost pixel = highest price
        low_y = max(col_bottoms)     # bottommost pixel = lowest price

        # body = the columns whose (top,bottom) span is the most common,
        # i.e. the widest part of the candle (wicks are thin outliers).
        spans = list(zip(col_tops, col_bottoms))
        # use median top/bottom across the widest half of columns as the body
        sorted_tops = sorted(col_tops)
        sorted_bottoms = sorted(col_bottoms)
        mid = len(sorted_tops) // 2
        body_top_y = sorted_tops[mid]
        body_bottom_y = sorted_bottoms[mid]

        # convert pixel-y to a relative price unit (invert: smaller y = higher price)
        def to_price(y: int) -> float:
            return round(float(height - y), 3)

        if is_bull:
            open_y, close_y = body_bottom_y, body_top_y
        else:
            open_y, close_y = body_top_y, body_bottom_y

        candles.append(
            {
                "open": to_price(open_y),
                "high": to_price(high_y),
                "low": to_price(low_y),
                "close": to_price(close_y),
                "direction_hint": "bullish" if is_bull else "bearish",
            }
        )

    candles = candles[-max_candles:]
    return {
        "candles": candles,
        "candle_count": len(candles),
        "note": (
            "Extracted from image colours; price levels are relative (no axis "
            "calibration), so trend/pattern direction is meaningful but absolute "
            "entry/stop/target values are illustrative, not real prices."
        ),
    }
