from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .admin import router as admin_router
from .auth import router as auth_router
from .auto_trade import router as auto_trade_router
from .billing import capabilities, router as billing_router, user_plan
from .chart_upload import router as chart_upload_router
from .mt5_bridge import router as mt5_bridge_router
from .backtest import run_backtest
from .data_feed import get_candles, get_live_price
from .db import init_db
from .fixtures import SYMBOLS
from .indicators import compute_indicators, latest_indicator_signals
from .patterns import detect_patterns
from .scoring import score_confluence
from .signal_job import (
    analyze_symbol_multi_timeframe,
    full_analysis,
    get_signal_history,
    get_signal_of_the_day,
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
    # Grade past News Intel predictions against the realized move, hourly.
    from .news_intel import grade_due_predictions

    scheduler.add_job(grade_due_predictions, "cron", minute=20, id="grade_news_intel")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


def _seed_admin():
    """Ensure a known admin account exists (verified, platinum) so the admin
    dashboard is always reachable. Override creds via env."""
    import os as _os

    from .db import db_session
    from .security import hash_password

    def _strip(val: str | None, default: str) -> str:
        v = (val or "").strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1].strip()
        return v or default

    email = _strip(_os.environ.get("ADMIN_EMAIL"), "admin@tradeinsight.app")
    password = _strip(_os.environ.get("ADMIN_PASSWORD"), "Admin1234!")
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
# Stray quote characters (from pasting KEY="value" into a raw env editor) are
# stripped per-origin so CORS doesn't silently fail to match the real Origin header.
import os as _os


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    return s


_origins = [_strip_quotes(o) for o in _os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
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
app.include_router(chart_upload_router)
app.include_router(mt5_bridge_router)


@app.get("/symbols")
def list_symbols():
    from .data_feed import data_source

    return {"symbols": SYMBOLS, "data_source": data_source()}


@app.get("/candles/{symbol}")
def get_candles_route(symbol: str, interval: str = "1day", count: int = 300):
    _validate_symbol(symbol)
    df = get_candles(symbol, interval=interval, count=count)
    return {"symbol": symbol, "interval": interval, "candles": df.to_dict(orient="records")}


@app.get("/price/{symbol}")
def get_price_route(symbol: str):
    """Exact-moment price, independent of candle bar granularity (candles only
    update once a bar closes; this is for a live ticker / chart last-bar patch)."""
    _validate_symbol(symbol)
    return {"symbol": symbol, **get_live_price(symbol)}


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
def get_backtest_route(symbol: str, interval: str = "1day", lookahead: int = 5, move_threshold: float | None = None):
    _validate_symbol(symbol)
    df = get_candles(symbol, interval=interval, count=300)
    return run_backtest(df, lookahead=lookahead, move_threshold=move_threshold, interval=interval)


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


def _mark_already_executed(signals: list[dict], user_id: int | None) -> list[dict]:
    """Flag signals the user's auto-trade bot has already opened a position
    from — the bot itself already refuses to reopen the same signal_id twice
    (see auto_trade.py's `taken` set), this just surfaces that fact in the UI
    so a signal that already fired isn't presented as still actionable."""
    if user_id is None or not signals:
        return signals
    from .db import db_session

    with db_session() as conn:
        rows = conn.execute(
            "SELECT signal_id, MIN(opened_at) AS executed_at FROM auto_trades "
            "WHERE user_id = ? AND signal_id IS NOT NULL GROUP BY signal_id",
            (user_id,),
        ).fetchall()
    executed = {r["signal_id"]: r["executed_at"] for r in rows}
    for s in signals:
        sid = s.get("id")
        if sid in executed:
            s["already_executed"] = True
            s["executed_at"] = executed[sid]
        else:
            s["already_executed"] = False
            s["executed_at"] = None
    return signals


@app.get("/signals/today")
def get_signals_today_route(symbol: str | None = None, x_user_id: int | None = Header(default=None)):
    signals = get_today_signal()
    if not signals:
        signals = run_daily_signal_scan()
    plan = user_plan(x_user_id)
    gated = _apply_plan_gate(signals, plan, symbol)
    return {"signals": _mark_already_executed(gated, x_user_id), "plan": plan}


@app.get("/signals/of-the-day")
def get_signal_of_the_day_route(x_user_id: int | None = Header(default=None)):
    """The single highest-composite-score setup across every symbol and
    timeframe scanned today — see get_signal_of_the_day's docstring for how
    "best" is computed honestly from the platform's own real numbers.

    Paying-customers-only feature: the Free plan (the only plan with
    `locked_symbols` set) always sees it locked, regardless of which symbol
    it happens to be — Signal of the Day isn't part of the free gold-only
    daily signal."""
    sotd = get_signal_of_the_day()
    plan = user_plan(x_user_id)
    if sotd is None:
        return {"signal": None, "plan": plan}

    caps = capabilities(plan)
    locked = bool(caps.get("locked_symbols"))  # only the Free plan has this set
    sotd = _mark_already_executed([sotd], x_user_id)[0]
    return {"signal": sotd, "locked": locked, "plan": plan}


@app.get("/signals/history")
def get_signals_history_route(limit: int = 30, symbol: str | None = None, x_user_id: int | None = Header(default=None)):
    plan = user_plan(x_user_id)
    if capabilities(plan).get("locked_symbols"):
        # free users (gold-only) don't get a full history feed
        return {"signals": [], "plan": plan}
    return {"signals": _mark_already_executed(get_signal_history(limit=limit), x_user_id), "plan": plan}


@app.post("/signals/run-now")
def run_signal_scan_now_route():
    return {"signals": run_daily_signal_scan()}


@app.get("/news-intel/xauusd")
def news_intel_route(x_user_id: int | None = Header(default=None)):
    """News Intel for gold: the current/next macro event (NFP, CPI, FOMC...)
    and the engine's live XAU/USD prediction with an honest, backtest-anchored
    probability. Paying-customers-only — the Free plan (gold-only daily signal)
    sees it locked, same gate as Signal of the Day."""
    from .news_intel import get_gold_events, get_news_intel

    plan = user_plan(x_user_id)
    locked = bool(capabilities(plan).get("locked_symbols"))  # only the Free plan
    if locked:
        # don't run the engine for locked users — just show the event calendar
        return {"locked": True, "plan": plan, "upcoming_events": get_gold_events()}
    return {"locked": False, "plan": plan, **get_news_intel()}


@app.get("/news-intel/history")
def news_intel_history_route(x_user_id: int | None = Header(default=None)):
    """Past News Intel predictions and their realized (graded) track record."""
    from .news_intel import accuracy_record, recent_predictions

    plan = user_plan(x_user_id)
    if capabilities(plan).get("locked_symbols"):
        return {"locked": True, "plan": plan, "track_record": accuracy_record()}
    return {"locked": False, "plan": plan, "predictions": recent_predictions(), "track_record": accuracy_record()}


@app.get("/debug/test-email")
def test_email_route(to: str = "test@example.com"):
    """Send a test email and return diagnostics — remove before go-live."""
    from .notify import (
        EMAIL_CONFIGURED,
        RESEND_API_KEY,
        RESEND_FROM,
        SMTP_FROM,
        SMTP_HOST,
        SMTP_PASS,
        SMTP_PORT,
        SMTP_USER,
        send_email,
    )

    config = {
        "smtp_user": SMTP_USER,
        "smtp_pass_set": bool(SMTP_PASS),
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_from": SMTP_FROM,
        "resend_key_set": bool(RESEND_API_KEY),
        "resend_from": RESEND_FROM,
        "email_configured": EMAIL_CONFIGURED,
    }
    sent = send_email(to, "PIP HIVE — test email", "If you see this, email delivery is working.")
    return {"sent": sent, "config": config}


@app.get("/learning/stats")
def learning_stats_route():
    """Adaptive learning: each strategy's win record + learned weight."""
    from .learning import stats

    return {"strategies": stats()}


@app.get("/api/v1/signals")
def public_signals_api(api_key: str):
    """Platinum programmatic access: returns today's signals for a valid API key."""
    from .db import db_session

    with db_session() as conn:
        row = conn.execute("SELECT plan, is_admin FROM users WHERE api_key = ?", (api_key,)).fetchone()
    if not row or (row["plan"] != "platinum" and not row["is_admin"]):
        raise HTTPException(status_code=401, detail="invalid or non-Platinum API key")
    return {"signals": get_today_signal(), "count": len(get_today_signal())}
