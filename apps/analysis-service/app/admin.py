"""View-only admin endpoints: read existing tables only, no destructive or
write actions exposed here. Every route requires a verified admin user_id."""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Header, HTTPException

from .data_feed import data_source as get_data_source
from .db import db_session
from .fixtures import SYMBOLS

router = APIRouter(prefix="/admin")


def _require_admin(x_user_id: int | None) -> None:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="missing X-User-Id header")
    with db_session() as conn:
        row = conn.execute("SELECT is_admin FROM users WHERE id = ?", (x_user_id,)).fetchone()
    if not row or not row["is_admin"]:
        raise HTTPException(status_code=403, detail="admin access required")


@router.get("/overview")
def overview(x_user_id: int | None = Header(default=None)):
    _require_admin(x_user_id)
    today = date.today().isoformat()
    with db_session() as conn:
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        signals_today = conn.execute("SELECT COUNT(*) AS c FROM signals WHERE date = ?", (today,)).fetchone()["c"]
        signals_total = conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()["c"]
        last_scan_rows = conn.execute(
            "SELECT symbol, MAX(date) AS last_date FROM signals GROUP BY symbol"
        ).fetchall()
        candle_rows = conn.execute(
            "SELECT symbol, COUNT(*) AS c, MAX(ts) AS last_ts FROM candles GROUP BY symbol"
        ).fetchall()

    candle_info = {r["symbol"]: {"candle_count": r["c"], "last_ts": r["last_ts"]} for r in candle_rows}
    data_source = get_data_source()

    return {
        "user_count": user_count,
        "signals_today": signals_today,
        "signals_total": signals_total,
        "data_source": data_source,
        "tracked_symbols": SYMBOLS,
        "last_signal_by_symbol": {r["symbol"]: r["last_date"] for r in last_scan_rows},
        "candle_cache": candle_info,
    }


@router.get("/users")
def list_users(x_user_id: int | None = Header(default=None)):
    _require_admin(x_user_id)
    with db_session() as conn:
        rows = conn.execute("SELECT id, email, is_admin, created_at FROM users ORDER BY id").fetchall()
    return {"users": [dict(r) for r in rows]}


@router.get("/signals")
def list_all_signals(limit: int = 200, x_user_id: int | None = Header(default=None)):
    _require_admin(x_user_id)
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY date DESC, confluence_score DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reasoning"] = json.loads(d.pop("reasoning_json"))
        if d.get("timeframes_agreed"):
            d["timeframes_agreed"] = json.loads(d["timeframes_agreed"])
        out.append(d)
    return {"signals": out}
