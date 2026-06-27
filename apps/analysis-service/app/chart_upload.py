"""Upload a chart screenshot and get the same rule-based analysis engine used
elsewhere on the platform — pattern detection, the 6-strategy consensus, trend
read, and illustrative trade levels. Gated by plan (Free = no uploads).

Honesty note carried through to the API response and the UI: because we
extract candles from image colour (no axis OCR), price levels are relative,
not the chart's real currency values. Trend/momentum/pattern direction is
still meaningful because that math is scale-invariant.
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from .billing import check_and_consume_upload_quota
from .chart_vision import extract_candles_from_image
from .indicators import compute_indicators, latest_indicator_signals
from .market_context import current_position
from .patterns import detect_all_patterns, detect_patterns
from .strategies import evaluate_strategies
from .trade_levels import compute_trade_levels

router = APIRouter(prefix="/charts")

MIN_CANDLES = 10
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/upload")
async def upload_chart(file: UploadFile = File(...), x_user_id: int | None = Header(default=None)):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="login required")
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
    levels = compute_trade_levels(result["direction"], close, atr, scoring_patterns)
    position = current_position(df, enriched, levels)

    return {
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
        "price_units": "relative (extracted from image, not the chart's real currency scale)",
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
