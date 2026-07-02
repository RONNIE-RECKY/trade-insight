"""Upload a chart screenshot and get the same rule-based analysis engine used
elsewhere on the platform — pattern detection, the 6-strategy consensus, trend
read, and illustrative trade levels. Gated by plan (Free = no uploads).

We try to read the pair, timeframe, and price axis straight off the image via
OCR (chart_vision.py) — if that works, `symbol`/`interval` are optional and
the price levels are REAL (axis-calibrated), not relative. OCR on a
screenshot is inherently imperfect though, so the caller can always pass
`symbol`/`interval` explicitly to override a wrong or missing detection, and
calibration falls back to relative (scale-invariant) units if the axis labels
weren't confidently readable. Either way, the authoritative trade plan is the
live multi-strategy/news/backtest engine run on the real current data for
whichever symbol/timeframe we ended up with — that's the one with a real,
executable price.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from .billing import check_and_consume_upload_quota
from .chart_vision import extract_candles_from_image
from .fixtures import SYMBOLS
from .indicators import compute_indicators, latest_indicator_signals
from .market_context import current_position
from .patterns import detect_all_patterns, detect_patterns
from .signal_job import full_analysis
from .strategies import evaluate_strategies
from .trade_levels import compute_trade_levels

router = APIRouter(prefix="/charts")

MIN_CANDLES = 10
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
VALID_INTERVALS = {"5min", "15min", "30min", "1h", "4h", "1day"}


@router.post("/upload")
async def upload_chart(
    file: UploadFile = File(...),
    symbol: str | None = Form(None),
    interval: str | None = Form(None),
    x_user_id: int | None = Header(default=None),
):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="login required")
    if symbol is not None and symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"unknown symbol '{symbol}', supported: {SYMBOLS}")
    if interval is not None and interval not in VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"unsupported interval '{interval}'")
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        raise HTTPException(status_code=400, detail="upload a PNG, JPEG or WEBP screenshot")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="image too large (max 8MB)")

    quota = check_and_consume_upload_quota(x_user_id)

    try:
        extracted = extract_candles_from_image(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"couldn't read that image: {e}")

    candles = extracted["candles"]
    if len(candles) < MIN_CANDLES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"only found {len(candles)} candles in that image (need at least {MIN_CANDLES}). "
                "Use a clearer, more zoomed-out candlestick screenshot with standard green/red colouring."
            ),
        )

    detected_symbol = extracted.get("detected_symbol")
    detected_interval = extracted.get("detected_interval")
    final_symbol = symbol or detected_symbol
    final_interval = interval or detected_interval or "1day"
    if not final_symbol:
        raise HTTPException(
            status_code=422,
            detail="couldn't detect which pair this screenshot is of — pick it from the symbol dropdown and try again.",
        )

    df = pd.DataFrame(candles)
    df["ts"] = range(len(df))  # no real timestamps from an image — sequential index

    enriched = compute_indicators(df)
    ind_signals = latest_indicator_signals(enriched)
    scoring_patterns = detect_patterns(df)
    all_patterns = detect_all_patterns(df)
    result = evaluate_strategies(ind_signals, scoring_patterns)

    last = enriched.iloc[-1]
    close = float(last["close"])
    atr = float(last["atr_14"]) if pd.notna(last.get("atr_14")) else None
    levels = compute_trade_levels(result["direction"], close, atr, scoring_patterns, result["confluence_score"])
    position = current_position(df, enriched, levels)

    # the authoritative trade plan: live data for the resolved symbol/timeframe,
    # run through the same multi-strategy + news + backtest engine as /analyze
    live = full_analysis(final_symbol, final_interval)

    return {
        "symbol": final_symbol,
        "interval": final_interval,
        "detected_symbol": detected_symbol,
        "detected_interval": detected_interval,
        "symbol_overridden": bool(symbol and detected_symbol and symbol != detected_symbol),
        "interval_overridden": bool(interval and detected_interval and interval != detected_interval),
        "calibrated": extracted.get("calibrated", False),
        "candle_count": len(candles),
        "direction": result["direction"],
        "confluence_score": result["confluence_score"],
        "strategies": result["strategies"],
        "strategy_agreement": result["strategy_agreement"],
        "patterns": all_patterns,
        "levels": levels,
        "current_position": position,
        "upload_quota": quota,
        "extraction_note": extracted["note"],
        "price_units": (
            "real (calibrated from the image's price axis)"
            if extracted.get("calibrated")
            else "relative (extracted from image, not the chart's real currency scale)"
        ),
        "live_analysis": live,
    }


@router.get("/upload-quota")
def upload_quota_status(x_user_id: int | None = Header(default=None)):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="login required")
    from .billing import capabilities, user_plan
    from .db import db_session

    plan = user_plan(x_user_id)
    quota = capabilities(plan).get("monthly_chart_uploads", 0)
    with db_session() as conn:
        row = conn.execute(
            "SELECT monthly_uploads_used, uploads_reset_at FROM users WHERE id = ?", (x_user_id,)
        ).fetchone()
    used = row["monthly_uploads_used"] if row else 0
    reset_at = row["uploads_reset_at"] if row else None
    from .billing import _now_str

    if not reset_at or reset_at <= _now_str():
        used = 0
    remaining = None if quota is None else max(0, quota - used)
    return {"quota": quota, "used": used, "remaining": remaining, "reset_at": reset_at}
