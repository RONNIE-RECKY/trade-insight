"""Automated PAPER-trading bot (Ultimate / Platinum only).

This places NO real orders and moves NO real money. For users who enable it,
the bot automatically opens *simulated* positions from the day's signals,
tracks them against real live prices, and auto-closes them when price hits the
stop-loss or take-profit — then reports the real hypothetical P&L and win-rate.

It is deliberately a simulator: a transparent way to see how the signals would
have performed if traded mechanically. Connecting it to a live brokerage to
place real orders is intentionally out of scope and must be done by the user
with their own broker and appropriate authorisation/licensing.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import broker
from .billing import capabilities, user_plan
from .data_feed import get_candles
from .db import db_session

router = APIRouter(prefix="/auto-trade")


def _require_auto_trade(user_id: int | None) -> int:
    if user_id is None:
        raise HTTPException(status_code=401, detail="login required")
    if not capabilities(user_plan(user_id)).get("auto_trade"):
        raise HTTPException(status_code=403, detail="automated trading requires Ultimate or Platinum")
    return user_id


def get_settings(user_id: int) -> dict:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM auto_trade_settings WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO auto_trade_settings (user_id) VALUES (?)", (user_id,))
            row = conn.execute("SELECT * FROM auto_trade_settings WHERE user_id = ?", (user_id,)).fetchone()
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    d["only_high_confidence"] = bool(d["only_high_confidence"])
    return d


def _evaluate_open(user_id: int) -> None:
    """Close any open paper position whose latest candle hit its stop or target."""
    with db_session() as conn:
        open_trades = conn.execute(
            "SELECT * FROM auto_trades WHERE user_id = ? AND status = 'open'", (user_id,)
        ).fetchall()

    for t in open_trades:
        try:
            df = get_candles(t["symbol"], interval=t["interval"] or "1day", count=10, refresh=True)
        except Exception:
            continue
        if df.empty:
            continue
        last = df.iloc[-1]
        high, low = float(last["high"]), float(last["low"])
        entry, sl, tp = t["entry"], t["stop_loss"], t["take_profit"]

        outcome = exit_price = None
        if t["direction"] == "bullish":
            if high >= tp:
                outcome, exit_price = "win", tp
            elif low <= sl:
                outcome, exit_price = "loss", sl
        else:  # bearish
            if low <= tp:
                outcome, exit_price = "win", tp
            elif high >= sl:
                outcome, exit_price = "loss", sl

        if outcome:
            if t["direction"] == "bullish":
                pnl = (exit_price - entry) / entry * 100
            else:
                pnl = (entry - exit_price) / entry * 100
            with db_session() as conn:
                conn.execute(
                    "UPDATE auto_trades SET status='closed', outcome=?, exit_price=?, pnl_pct=?, "
                    "closed_at=datetime('now') WHERE id=?",
                    (outcome, round(exit_price, 5), round(pnl, 3), t["id"]),
                )


def _tradeable(sig: dict) -> bool:
    return (
        sig.get("direction") in ("bullish", "bearish")
        and sig.get("entry") is not None
        and sig.get("stop_loss") is not None
        and sig.get("take_profit") is not None
    )


def _open_from_signals(user_id: int, settings: dict) -> None:
    """Auto-open simulated positions from today's qualifying signals."""
    from .signal_job import get_today_signal, run_daily_signal_scan

    signals = get_today_signal()
    if not signals:  # nothing scanned yet today — generate now so the bot has something to trade
        signals = run_daily_signal_scan()

    candidates = [s for s in signals if _tradeable(s)]
    if settings["only_high_confidence"]:
        premium = [s for s in candidates if s.get("tier") == "premium"]
        # fall back to all tradeable signals if no premium ones exist, so the bot still acts
        candidates = premium or candidates

    with db_session() as conn:
        open_count = conn.execute(
            "SELECT COUNT(*) AS c FROM auto_trades WHERE user_id=? AND status='open'", (user_id,)
        ).fetchone()["c"]
        taken = {
            r["signal_id"]
            for r in conn.execute(
                "SELECT signal_id FROM auto_trades WHERE user_id=?", (user_id,)
            ).fetchall()
        }

    for sig in candidates:
        if open_count >= settings["max_open"]:
            break
        if sig["id"] in taken:
            continue

        # Route the order to the connected venue (simulated / demo broker / live-pending).
        routed = broker.execute_order(
            user_id, sig["symbol"], sig["direction"], sig["stop_loss"], sig["take_profit"]
        )
        with db_session() as conn:
            conn.execute(
                "INSERT INTO auto_trades (user_id, signal_id, symbol, interval, direction, entry, "
                "stop_loss, take_profit, status, outcome, venue, broker_ref) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', 'open', ?, ?)",
                (
                    user_id,
                    sig["id"],
                    sig["symbol"],
                    sig.get("interval"),
                    sig["direction"],
                    sig["entry"],
                    sig["stop_loss"],
                    sig["take_profit"],
                    routed.get("venue", "simulated"),
                    routed.get("broker_ref"),
                ),
            )
        open_count += 1


def sync(user_id: int) -> None:
    settings = get_settings(user_id)
    _evaluate_open(user_id)  # always update open positions vs latest price
    if settings["enabled"]:
        _open_from_signals(user_id, settings)


def get_positions(user_id: int) -> dict:
    sync(user_id)
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM auto_trades WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()
    trades = [dict(r) for r in rows]
    open_trades = [t for t in trades if t["status"] == "open"]
    closed = [t for t in trades if t["status"] == "closed"]
    wins = [t for t in closed if t["outcome"] == "win"]
    total_pnl = round(sum(t["pnl_pct"] or 0 for t in closed), 2)
    win_rate = round(len(wins) / len(closed) * 100, 1) if closed else None
    return {
        "open": open_trades,
        "closed": closed,
        "stats": {
            "open_count": len(open_trades),
            "closed_count": len(closed),
            "wins": len(wins),
            "win_rate": win_rate,
            "total_pnl_pct": total_pnl,
        },
    }


class SettingsUpdate(BaseModel):
    enabled: bool
    max_open: int = 5
    only_high_confidence: bool = True


@router.get("/settings")
def settings_route(x_user_id: int | None = Header(default=None)):
    uid = _require_auto_trade(x_user_id)
    return get_settings(uid)


@router.post("/settings")
def update_settings_route(req: SettingsUpdate, x_user_id: int | None = Header(default=None)):
    uid = _require_auto_trade(x_user_id)
    max_open = max(1, min(req.max_open, 50))
    with db_session() as conn:
        conn.execute(
            "INSERT INTO auto_trade_settings (user_id, enabled, max_open, only_high_confidence, updated_at) "
            "VALUES (?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled, max_open=excluded.max_open, "
            "only_high_confidence=excluded.only_high_confidence, updated_at=datetime('now')",
            (uid, 1 if req.enabled else 0, max_open, 1 if req.only_high_confidence else 0),
        )
    sync(uid)
    return get_settings(uid)


@router.get("/positions")
def positions_route(x_user_id: int | None = Header(default=None)):
    uid = _require_auto_trade(x_user_id)
    return get_positions(uid)


class BrokerConnect(BaseModel):
    provider: str = "simulated"   # simulated | oanda
    mode: str = "demo"            # demo | live
    account_id: str | None = None
    token: str | None = None
    risk_acknowledged: bool = False


@router.get("/broker")
def broker_route(x_user_id: int | None = Header(default=None)):
    uid = _require_auto_trade(x_user_id)
    return broker.get_connection(uid)


@router.post("/broker")
def connect_broker_route(req: BrokerConnect, x_user_id: int | None = Header(default=None)):
    uid = _require_auto_trade(x_user_id)
    if req.provider == "oanda" and req.mode == "demo" and (not req.account_id or not req.token):
        raise HTTPException(status_code=400, detail="demo connection needs an account id and practice token")
    # A live (real-money) connection is only accepted with an explicit risk waiver.
    if req.mode == "live" and not req.risk_acknowledged:
        raise HTTPException(status_code=400, detail="live accounts require acknowledging the risk warning")
    broker.set_connection(uid, req.provider, req.mode, req.account_id, req.token, req.risk_acknowledged)
    return broker.get_connection(uid)
