from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .admin import router as admin_router
from .auth import router as auth_router
from .auto_trade import router as auto_trade_router
from .billing import capabilities, router as billing_router, user_plan
from .backtest import run_backtest
from .data_feed import get_candles
from .db import init_db
from .fixtures import SYMBOLS
from .indicators import compute_indicators, latest_indicator_signals
from .patterns import detect_patterns
from .scoring import score_confluence
from .signal_job import (
    analyze_symbol_multi_timeframe,
    full_analysis,
    get_signal_history,
    get_today_signal,
    predict_symbol_timeframes,
    run_daily_signal_scan,
)

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_admin()
    scheduler.add_job(run_daily_signal_scan, "cron", hour=0, minute=5, id="daily_signal_scan")
    # Pre-warm today's signals shortly after boot so the first page load is instant.
    scheduler.add_job(_prewarm_signals, "date", id="prewarm_signals")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


def _seed_admin():
    """Ensure a known admin account exists (verified, platinum) so the admin
    dashboard is always reachable. Override creds via env."""
    import os

    from .auth import hash_password
    from .db import db_session

    email = os.environ.get("ADMIN_EMAIL", "admin@tradeinsight.app")
    password = os.environ.get("ADMIN_PASSWORD", "Admin1234!")
    with db_session() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return
        conn.execute(
            "INSERT INTO users (email, password_hash, is_admin, plan, verified) VALUES (?, ?, 1, 'platinum', 1)",
            (email, hash_password(password)),
        )


def _prewarm_signals():
    if not get_today_signal():
        run_daily_signal_scan()


app = FastAPI(title="Trade Insight Analysis Service", lifespan=lifespan)

# Allowed frontend origins. In production set ALLOWED_ORIGINS to a comma-separated
# list of your deployed web URLs (e.g. "https://web-production.up.railway.app").
import os as _os

_origins = [o.strip() for o in _os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_symbol(symbol: str) -> None:
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"unknown symbol '{symbol}', supported: {SYMBOLS}")


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(auto_trade_router)


@app.get("/symbols")
def list_symbols():
    from .data_feed import data_source

    return {"symbols": SYMBOLS, "data_source": data_source()}


@app.get("/candles/{symbol}")
def get_candles_route(symbol: str, interval: str = "1day", count: int = 300):
    _validate_symbol(symbol)
    df = get_candles(symbol, interval=interval, count=count)
    return {"symbol": symbol, "interval": interval, "candles": df.to_dict(orient="records")}


@app.get("/analysis/{symbol}")
def get_analysis_route(symbol: str, interval: str = "1day"):
    _validate_symbol(symbol)
    df = get_candles(symbol, interval=interval, count=300)
    enriched = compute_indicators(df)
    ind_signals = latest_indicator_signals(enriched)
    pats = detect_patterns(df)
    result = score_confluence(ind_signals, pats)
    return {
        "symbol": symbol,
        "interval": interval,
        **result,
        "indicators": enriched.tail(60).fillna("NaN").to_dict(orient="records"),
    }


@app.get("/analysis/{symbol}/multi-timeframe")
def get_multi_timeframe_route(symbol: str):
    _validate_symbol(symbol)
    return analyze_symbol_multi_timeframe(symbol)


@app.get("/predictions/{symbol}")
def get_predictions_route(symbol: str):
    _validate_symbol(symbol)
    return {"symbol": symbol, "predictions": predict_symbol_timeframes(symbol)}


@app.get("/analyze/{symbol}")
def analyze_route(symbol: str, interval: str = "1h", x_user_id: int | None = Header(default=None)):
    _validate_symbol(symbol)
    if interval not in {"5min", "15min", "30min", "1h", "4h", "1day"}:
        raise HTTPException(status_code=400, detail=f"unsupported interval '{interval}'")
    caps = capabilities(user_plan(x_user_id))
    if interval not in caps["timeframes"]:
        raise HTTPException(
            status_code=403,
            detail=f"the {interval} timeframe requires a higher plan",
        )
    return full_analysis(symbol, interval)


@app.get("/analyze/{symbol}/export")
def export_analysis_route(
    symbol: str,
    interval: str = "1h",
    format: str = "json",
    x_user_id: int | None = Header(default=None),
):
    _validate_symbol(symbol)
    caps = capabilities(user_plan(x_user_id))
    if not caps["export"]:
        raise HTTPException(status_code=403, detail="export requires a paid plan")
    if interval not in caps["timeframes"]:
        raise HTTPException(status_code=403, detail=f"the {interval} timeframe requires a higher plan")

    report = full_analysis(symbol, interval)

    if format == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["pattern", "direction", "points"])
        for p in report["patterns"]:
            pts = " | ".join(f"{pt['ts']}@{pt['price']}" for pt in p["points"])
            writer.writerow([p["pattern"], p["direction"], pts])
        writer.writerow([])
        writer.writerow(["strategy", "signal", "reason"])
        for s in report.get("strategies", []):
            writer.writerow([s["name"], s["signal"], s["reason"]])
        from fastapi.responses import Response

        filename = f"{symbol}_{interval}_analysis.csv"
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    from fastapi.responses import JSONResponse

    filename = f"{symbol}_{interval}_analysis.json"
    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/backtest/{symbol}")
def get_backtest_route(symbol: str, interval: str = "1day", lookahead: int = 5, move_threshold: float = 0.005):
    _validate_symbol(symbol)
    df = get_candles(symbol, interval=interval, count=300)
    return run_backtest(df, lookahead=lookahead, move_threshold=move_threshold)


def _apply_plan_gate(signals: list[dict], plan: str, symbol: str | None) -> list[dict]:
    """Enforce per-plan limits on the signal feed:
    - Free: locked to its single symbol (gold) and one daily signal.
    - Paid: capped to the plan's max_daily_signals (Pro 10, Ultimate 40,
      Platinum unlimited); premium cards are surfaced and locked client-side.
    """
    caps = capabilities(plan)
    locked = caps.get("locked_symbols")
    cap = caps["max_daily_signals"]

    if locked:
        daily_tf = caps["timeframes"][0] if caps["timeframes"] else "1day"
        filtered = [s for s in signals if s.get("symbol") == locked[0] and s.get("interval") == daily_tf]
        return filtered[: (cap or 1)]

    if cap is None:
        return signals
    return signals[:cap]


@app.get("/signals/today")
def get_signals_today_route(symbol: str | None = None, x_user_id: int | None = Header(default=None)):
    signals = get_today_signal()
    if not signals:
        signals = run_daily_signal_scan()
    plan = user_plan(x_user_id)
    return {"signals": _apply_plan_gate(signals, plan, symbol), "plan": plan}


@app.get("/signals/history")
def get_signals_history_route(limit: int = 30, symbol: str | None = None, x_user_id: int | None = Header(default=None)):
    plan = user_plan(x_user_id)
    if capabilities(plan).get("locked_symbols"):
        # free users (gold-only) don't get a full history feed
        return {"signals": [], "plan": plan}
    return {"signals": get_signal_history(limit=limit), "plan": plan}


@app.post("/signals/run-now")
def run_signal_scan_now_route():
    return {"signals": run_daily_signal_scan()}
