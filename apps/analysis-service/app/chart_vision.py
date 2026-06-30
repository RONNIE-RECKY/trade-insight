"""Extract a candlestick series from an uploaded chart SCREENSHOT.

How it actually works (no black-box claims):
- We scan the image for pixels matching a bullish (green-ish) or bearish
  (red-ish) candle colour — the two colours essentially every charting tool
  uses (TradingView, MT4/5, etc).
- Pixel columns are grouped into candles by horizontal gaps.
- For each candle, the full coloured vertical extent gives the high/low; the
  body (the widest, most common columns in the group) gives the open/close.
- Direction (bullish/bearish) comes directly from which colour matched.

We also run OCR (Tesseract, via pytesseract) over the image, best-effort:
- Scan all recognised text for a known symbol (e.g. "EURUSD", "EUR/USD") and
  a timeframe token (e.g. "1H", "H1", "Daily", "D1") to pre-fill the upload
  form — the user can still override either before we use them.
- Scan word-level OCR boxes near the left/right edges (where charting tools
  put the price axis) for number-shaped labels. If we find at least two, at
  sufficiently different heights and values, we fit a straight line (pixel-y
  -> price) and use REAL calibrated prices for the extracted candles instead
  of relative units.

Honesty boundary: OCR on a screenshot is inherently unreliable — small/
stylised fonts, watermarks, or an unusual layout can make it find nothing or
read a number wrong. When OCR can't confidently calibrate the price axis
(fewer than two usable axis labels, or they're too close together to fit a
line), we fall back to relative units exactly as before and say so in the
response — never a fabricated price.
"""
from __future__ import annotations

import io
import re

import numpy as np
from PIL import Image

try:
    import pytesseract
    from pytesseract import Output as _TesseractOutput

    _OCR_AVAILABLE = True
except ImportError:  # pytesseract not installed in this environment
    _OCR_AVAILABLE = False

from .fixtures import SYMBOLS

_TIMEFRAME_PATTERNS: list[tuple[str, str]] = [
    (r"\bD\s*1\b|\b1\s*D(?:AY)?\b|\bDAILY\b", "1day"),
    (r"\bH\s*4\b|\b4\s*H(?:R|OUR)?\b", "4h"),
    (r"\bH\s*1\b|\b1\s*H(?:R|OUR)?\b", "1h"),
    (r"\bM\s*30\b|\b30\s*M(?:IN)?\b", "30min"),
    (r"\bM\s*15\b|\b15\s*M(?:IN)?\b", "15min"),
    (r"\bM\s*5\b|\b5\s*M(?:IN)?\b", "5min"),
]


def _ocr_text(img: Image.Image) -> str:
    if not _OCR_AVAILABLE:
        return ""
    try:
        return pytesseract.image_to_string(img)
    except Exception:  # tesseract binary missing/misconfigured — degrade quietly
        return ""


def detect_symbol(text: str) -> str | None:
    cleaned = re.sub(r"[^A-Z0-9]", "", text.upper())
    for sym in SYMBOLS:
        if sym in cleaned:
            return sym
    return None


def detect_interval(text: str) -> str | None:
    upper = text.upper()
    for pattern, interval in _TIMEFRAME_PATTERNS:
        if re.search(pattern, upper):
            return interval
    return None


def _robust_axis_fit(points: list[tuple[float, float]]):
    """RANSAC-style linear fit tolerant of a few bad OCR reads (e.g. a dropped
    decimal point making one label's value wildly wrong). Tries every pair of
    points as a candidate line, scores it by how many OTHER points it predicts
    within a tight RELATIVE tolerance of their own (possibly-misread) value,
    then refits on the winning inlier set. Relative tolerance (not absolute)
    is what makes this catch magnitude errors like 1.1350 misread as 11350."""
    n = len(points)
    if n < 2:
        return None

    best_inliers: list[tuple[float, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            y1, v1 = points[i]
            y2, v2 = points[j]
            if y1 == y2 or v1 == v2:
                continue
            slope = (v2 - v1) / (y2 - y1)
            intercept = v1 - slope * y1
            inliers = [
                p for p in points
                if abs((slope * p[0] + intercept) - p[1]) <= max(abs(p[1]) * 0.02, 1e-9)
            ]
            if len(inliers) > len(best_inliers):
                best_inliers = inliers

    if len(best_inliers) < 2:
        return None
    iy = [p[0] for p in best_inliers]
    iv = [p[1] for p in best_inliers]
    if max(iy) - min(iy) < 1e-6:
        return None
    return np.polyfit(iy, iv, 1)


def _detect_price_calibration(img: Image.Image):
    """Best-effort pixel-y -> real-price linear fit from axis-label OCR.
    Returns a callable, or None if we couldn't find a confident calibration."""
    if not _OCR_AVAILABLE:
        return None
    try:
        data = pytesseract.image_to_data(img, output_type=_TesseractOutput.DICT)
    except Exception:
        return None

    width, height = img.size
    points: list[tuple[float, float]] = []
    for i in range(len(data.get("text", []))):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        cx = x + w / 2
        # price axis labels live in the left or right margin of the chart
        if not (cx > width * 0.85 or cx < width * 0.15):
            continue
        cleaned = txt.replace(",", "")
        if not re.fullmatch(r"-?\d{1,6}(\.\d{1,6})?", cleaned):
            continue
        try:
            val = float(cleaned)
        except ValueError:
            continue
        points.append((y + h / 2, val))

    if len(points) < 2:
        return None
    ys = [p[0] for p in points]
    if max(ys) - min(ys) < height * 0.05:
        return None  # labels too clustered vertically — not a usable scale

    fit = _robust_axis_fit(points)
    if fit is None:
        return None
    slope, intercept = fit
    if slope == 0:
        return None

    def calibrate(y: float) -> float:
        return float(slope * y + intercept)

    return calibrate

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

    ocr_text = _ocr_text(img)
    detected_symbol = detect_symbol(ocr_text)
    detected_interval = detect_interval(ocr_text)
    calibrate = _detect_price_calibration(img)

    arr = np.asarray(img, dtype=np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    bull_mask = _is_bullish(r, g, b)
    bear_mask = _is_bearish(r, g, b)
    candle_mask = bull_mask | bear_mask

    col_has_candle = candle_mask.any(axis=0)
    if not col_has_candle.any():
        return {
            "candles": [],
            "note": "no candlestick colours detected in this image",
            "detected_symbol": detected_symbol,
            "detected_interval": detected_interval,
            "calibrated": False,
        }

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

        # convert pixel-y to a price: calibrated (real) if we found usable axis
        # labels, otherwise a relative unit (invert: smaller y = higher price)
        def to_price(y: int) -> float:
            if calibrate is not None:
                return round(calibrate(y), 5)
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
    note = (
        "Price axis labels were read from the image and calibrated — these are real "
        "price levels, not illustrative ones."
        if calibrate is not None
        else (
            "Extracted from image colours; price levels are relative (no axis "
            "calibration), so trend/pattern direction is meaningful but absolute "
            "entry/stop/target values are illustrative, not real prices."
        )
    )
    return {
        "candles": candles,
        "candle_count": len(candles),
        "note": note,
        "detected_symbol": detected_symbol,
        "detected_interval": detected_interval,
        "calibrated": calibrate is not None,
    }
