"""MT5 Expert Advisor bridge — DEMO accounts auto-execute; LIVE accounts
require the user to confirm each trade first.

Demo flow:
1. A user with Ultimate/Platinum connects their MT5 DEMO account and gets an
   API key, installs the companion EA, pastes the key into its inputs.
2. The bot queues orders from qualifying signals into `auto_trades` with
   venue='mt5-demo', delivery_status='ready' immediately — no confirmation.
3. The EA polls GET /mt5/orders, executes, reports back via POST /mt5/result.

Live flow (real money — never unsupervised):
1. The user connects a LIVE MT5 account via POST /mt5/connect-live, which
   requires risk_acknowledged=true.
2. The bot still queues an order per qualifying signal, but with
   venue='mt5-live' and delivery_status='awaiting_confirmation' — the EA
   poller will NOT see it yet. A confirmation email is sent with a one-click
   link, and the trade also shows up in GET /mt5/pending for an in-app
   "Confirm & Execute" button.
3. Only once the user confirms (POST /mt5/confirm/{id} or the emailed link,
   GET /mt5/confirm-link/{token}) does delivery_status flip to 'ready', so
   the EA picks it up on its next poll. If nobody confirms within
   CONFIRM_WINDOW_MINUTES, the trade expires and is never sent.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .billing import capabilities, user_plan
from .db import db_session
from .notify import WEB_BASE_URL, send_email
from .security import sanitize_token_field

router = APIRouter(prefix="/mt5")

# How long a live trade's confirmation offer stays valid before it expires
# unconfirmed. Keeps a stale signal from being executed hours later at a price
# that no longer reflects the original setup.
CONFIRM_WINDOW_MINUTES = 15


def new_confirm_token() -> str:
    return secrets.token_urlsafe(32)


def _user_email(user_id: int) -> str | None:
    with db_session() as conn:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["email"] if row else None


def notify_pending_confirmation(user_id: int, trade_id: int, signal: dict, confirm_token: str) -> None:
    """Email the user a one-click link to confirm (and thereby execute) a
    live trade. Best-effort — the in-app /mt5/pending list + Confirm button
    still works even if the email never arrives."""
    email = _user_email(user_id)
    if not email:
        return
    link = f"{WEB_BASE_URL}/confirm-trade?token={confirm_token}"
    direction = "BUY" if signal.get("direction") == "bullish" else "SELL"
    subject = f"Confirm live trade: {direction} {signal.get('symbol')}"
    body = (
        f"PIP HIVE generated a new {direction} signal for {signal.get('symbol')}:\n\n"
        f"  Entry: {signal.get('entry')}\n  Stop loss: {signal.get('stop_loss')}\n"
        f"  Take profit: {signal.get('take_profit')}\n\n"
        f"Confirm to execute it on your live MT5 account:\n{link}\n\n"
        f"This offer expires in {CONFIRM_WINDOW_MINUTES} minutes. If you don't confirm, "
        "it will NOT be executed."
    )
    send_email(email, subject, body)


def _expire_stale(user_id: int | None = None) -> None:
    """Close out any live trade whose confirmation window has passed without
    being confirmed, so the EA never sees it."""
    with db_session() as conn:
        if user_id is None:
            conn.execute(
                "UPDATE auto_trades SET status='closed', outcome='expired', delivery_status='expired', "
                "closed_at=datetime('now') WHERE venue='mt5-live' AND delivery_status='awaiting_confirmation' "
                "AND confirm_expires_at < datetime('now')"
            )
        else:
            conn.execute(
                "UPDATE auto_trades SET status='closed', outcome='expired', delivery_status='expired', "
                "closed_at=datetime('now') WHERE user_id=? AND venue='mt5-live' "
                "AND delivery_status='awaiting_confirmation' AND confirm_expires_at < datetime('now')",
                (user_id,),
            )


def _require_entitled(user_id: int | None) -> int:
    if user_id is None:
        raise HTTPException(status_code=401, detail="login required")
    if not capabilities(user_plan(user_id)).get("auto_trade"):
        raise HTTPException(status_code=403, detail="the MT5 bridge requires Ultimate or Platinum")
    return user_id


def _user_id_for_api_key(api_key: str) -> int | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT user_id FROM broker_connections WHERE provider = 'mt5' AND token = ?", (api_key,)
        ).fetchone()
    return row["user_id"] if row else None


class ConnectRequest(BaseModel):
    account_id: str | None = None  # the user's MT5 login number, for their own reference only


class ConnectLiveRequest(BaseModel):
    account_id: str | None = None
    risk_acknowledged: bool = False


@router.post("/connect")
def connect(req: ConnectRequest, x_user_id: int | None = Header(default=None)):
    """Generate (or rotate) the API key for this user's MT5 EA, DEMO mode.
    Orders queued under this connection auto-execute with no confirmation."""
    uid = _require_entitled(x_user_id)
    account_id = sanitize_token_field(req.account_id) if req.account_id else None
    api_key = "mt5_" + secrets.token_urlsafe(24)
    with db_session() as conn:
        conn.execute(
            "INSERT INTO broker_connections (user_id, provider, mode, account_id, token, updated_at) "
            "VALUES (?, 'mt5', 'demo', ?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET provider='mt5', mode='demo', account_id=excluded.account_id, "
            "token=excluded.token, updated_at=datetime('now')",
            (uid, account_id, api_key),
        )
    return {"provider": "mt5", "mode": "demo", "account_id": account_id, "api_key": api_key}


@router.post("/connect-live")
def connect_live(req: ConnectLiveRequest, x_user_id: int | None = Header(default=None)):
    """Generate (or rotate) the API key for this user's MT5 EA, LIVE mode.
    Every order queued under this connection requires the user to confirm
    before the EA bridge will deliver it (see notify_pending_confirmation)."""
    uid = _require_entitled(x_user_id)
    if not req.risk_acknowledged:
        raise HTTPException(status_code=400, detail="you must acknowledge the live-trading risk to connect a live account")
    account_id = sanitize_token_field(req.account_id) if req.account_id else None
    api_key = "mt5_" + secrets.token_urlsafe(24)
    with db_session() as conn:
        conn.execute(
            "INSERT INTO broker_connections (user_id, provider, mode, account_id, token, risk_acknowledged, updated_at) "
            "VALUES (?, 'mt5', 'live', ?, ?, 1, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET provider='mt5', mode='live', account_id=excluded.account_id, "
            "token=excluded.token, risk_acknowledged=1, updated_at=datetime('now')",
            (uid, account_id, api_key),
        )
    return {"provider": "mt5", "mode": "live", "account_id": account_id, "api_key": api_key}


@router.get("/pending")
def pending_confirmations(x_user_id: int | None = Header(default=None)):
    """Live trades awaiting the user's confirmation, for the in-app
    'Confirm & Execute' button."""
    uid = _require_entitled(x_user_id)
    _expire_stale(uid)
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, symbol, interval, direction, entry, stop_loss, take_profit, confirm_expires_at "
            "FROM auto_trades WHERE user_id = ? AND venue = 'mt5-live' AND delivery_status = 'awaiting_confirmation' "
            "ORDER BY id DESC",
            (uid,),
        ).fetchall()
    return {"pending": [dict(r) for r in rows]}


def _confirm_trade(trade_id: int, uid: int | None = None) -> bool:
    """Flip a trade from awaiting_confirmation to ready so the EA's next poll
    picks it up. Returns False if it doesn't exist, isn't pending, or expired."""
    with db_session() as conn:
        if uid is not None:
            row = conn.execute(
                "SELECT id FROM auto_trades WHERE id = ? AND user_id = ? AND venue = 'mt5-live' "
                "AND delivery_status = 'awaiting_confirmation' AND confirm_expires_at >= datetime('now')",
                (trade_id, uid),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM auto_trades WHERE id = ? AND venue = 'mt5-live' "
                "AND delivery_status = 'awaiting_confirmation' AND confirm_expires_at >= datetime('now')",
                (trade_id,),
            ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE auto_trades SET delivery_status = 'ready', confirmed_at = datetime('now') WHERE id = ?",
            (trade_id,),
        )
    return True


@router.post("/confirm/{trade_id}")
def confirm_trade(trade_id: int, x_user_id: int | None = Header(default=None)):
    uid = _require_entitled(x_user_id)
    _expire_stale(uid)
    if not _confirm_trade(trade_id, uid):
        raise HTTPException(status_code=409, detail="trade not found, already handled, or its confirmation window expired")
    return {"ok": True}


@router.get("/confirm-link/{token}", response_class=HTMLResponse)
def confirm_via_link(token: str):
    """Public (unauthenticated) confirm link clicked from the email. The
    token is single-purpose and tied to one trade, so no login is needed."""
    _expire_stale()
    with db_session() as conn:
        row = conn.execute(
            "SELECT id FROM auto_trades WHERE confirm_token = ? AND venue = 'mt5-live'", (token,)
        ).fetchone()
    if row and _confirm_trade(row["id"]):
        return "<html><body><h2>Trade confirmed.</h2><p>It will execute on your MT5 terminal shortly.</p></body></html>"
    return "<html><body><h2>This confirmation link is no longer valid.</h2><p>It may have already been used or expired.</p></body></html>"


@router.get("/orders")
def get_orders(api_key: str):
    """Polled by the EA. Returns ready-to-execute orders (demo, or live ones
    the user has already confirmed) and marks them delivered so they aren't
    returned again on the next poll."""
    uid = _user_id_for_api_key(api_key)
    if uid is None:
        raise HTTPException(status_code=401, detail="unknown or revoked API key")

    _expire_stale(uid)
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, symbol, direction, entry, stop_loss, take_profit, lot_size FROM auto_trades "
            "WHERE user_id = ? AND venue IN ('mt5-demo', 'mt5-live') AND status = 'open' AND delivery_status = 'ready'",
            (uid,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE auto_trades SET delivery_status = 'sent' WHERE id IN ({placeholders})", ids
            )

    return {
        "orders": [
            {
                "id": r["id"],
                "symbol": r["symbol"],
                "action": "BUY" if r["direction"] == "bullish" else "SELL",
                "lot": r["lot_size"] or 0.1,
                "sl": r["stop_loss"],
                "tp": r["take_profit"],
            }
            for r in rows
        ]
    }


class OrderResult(BaseModel):
    api_key: str
    order_id: int
    status: str  # filled | failed
    ticket: str | None = None
    fill_price: float | None = None


@router.post("/result")
def report_result(req: OrderResult):
    """The EA reports back whether it actually executed the order on the
    demo terminal, and the resulting ticket/fill price."""
    uid = _user_id_for_api_key(req.api_key)
    if uid is None:
        raise HTTPException(status_code=401, detail="unknown or revoked API key")

    with db_session() as conn:
        row = conn.execute(
            "SELECT id FROM auto_trades WHERE id = ? AND user_id = ? AND venue IN ('mt5-demo', 'mt5-live')",
            (req.order_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="order not found")

        if req.status == "filled":
            conn.execute(
                "UPDATE auto_trades SET broker_ref = ? WHERE id = ?",
                (req.ticket or "filled", req.order_id),
            )
        else:
            # execution failed on the terminal (e.g. market closed, requote) —
            # release it back so the next poll picks it up and retries.
            conn.execute(
                "UPDATE auto_trades SET delivery_status = 'ready', broker_ref = ? WHERE id = ?",
                (f"retry:{req.status}", req.order_id),
            )
    return {"ok": True}


@router.delete("/connect")
def disconnect(x_user_id: int | None = Header(default=None)):
    uid = _require_entitled(x_user_id)
    with db_session() as conn:
        conn.execute(
            "UPDATE broker_connections SET provider='simulated', token=NULL, account_id=NULL "
            "WHERE user_id = ? AND provider = 'mt5'",
            (uid,),
        )
    return {"ok": True}
