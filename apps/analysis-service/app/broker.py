"""Brokerage connection + order routing.

Safety model (intentional, non-negotiable): this platform only ever connects
to DEMO / practice accounts for automated execution.
- "simulated" → internal paper trades only. Default. No external calls.
- "demo"      → real orders against a broker PRACTICE account (OANDA fxpractice,
                or an MT5 demo account via the EA bridge in mt5_bridge.py).
                Authentic execution, but the money is fake. The bot may do this
                autonomously.

There is intentionally no "live" (real-money) mode anywhere in this file or
its callers. Connecting a real brokerage account for unsupervised automated
execution is out of scope for this platform — full stop, not configurable.
"""
from __future__ import annotations

import httpx

from .db import db_session

OANDA_PRACTICE = "https://api-fxpractice.oanda.com"
OANDA_LIVE = "https://api-fxtrade.oanda.com"


def _oanda_instrument(symbol: str) -> str | None:
    """Map our symbol to an OANDA instrument, or None if unsupported there."""
    fx = {
        "EURUSD": "EUR_USD", "GBPUSD": "GBP_USD", "USDJPY": "USD_JPY",
        "USDCHF": "USD_CHF", "AUDUSD": "AUD_USD", "USDCAD": "USD_CAD",
        "NZDUSD": "NZD_USD", "XAUUSD": "XAU_USD",
    }
    return fx.get(symbol)


def get_connection(user_id: int) -> dict:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM broker_connections WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return {"provider": "simulated", "mode": "demo", "connected": False, "risk_acknowledged": False}
    d = dict(row)
    return {
        "provider": d["provider"],
        "mode": d["mode"],
        "account_id": d["account_id"],
        "connected": d["provider"] != "simulated",
        "risk_acknowledged": bool(d["risk_acknowledged"]),
        "has_token": bool(d["token"]),
    }


def set_connection(user_id: int, provider: str, mode: str, account_id: str | None,
                   token: str | None, risk_acknowledged: bool) -> None:
    with db_session() as conn:
        conn.execute(
            "INSERT INTO broker_connections (user_id, provider, mode, account_id, token, risk_acknowledged, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET provider=excluded.provider, mode=excluded.mode, "
            "account_id=excluded.account_id, token=excluded.token, risk_acknowledged=excluded.risk_acknowledged, "
            "updated_at=datetime('now')",
            (user_id, provider, mode, account_id, token, 1 if risk_acknowledged else 0),
        )


def _raw_connection(user_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM broker_connections WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def execute_order(user_id: int, symbol: str, direction: str, stop_loss: float,
                  take_profit: float, units: int = 1000) -> dict:
    """Route an order according to the user's DEMO broker connection.

    Returns a dict describing where the order went:
      {"venue": "simulated"}                  → caller records a paper trade
      {"venue": "demo", "broker_ref": "..."}  → real order placed on practice acct

    MT5 connections are NOT routed through here — MT5 has no push API, so its
    orders are queued for the polling EA instead (see mt5_bridge.py).
    """
    raw = _raw_connection(user_id)
    if not raw or raw["provider"] in ("simulated", "mt5"):
        return {"venue": "simulated"}

    if raw["provider"] == "oanda" and raw["mode"] == "demo":
        instrument = _oanda_instrument(symbol)
        if not instrument or not raw.get("token") or not raw.get("account_id"):
            return {"venue": "simulated", "reason": "unsupported instrument or missing demo credentials"}
        signed_units = units if direction == "bullish" else -units
        payload = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(signed_units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": f"{stop_loss:.5f}"},
                "takeProfitOnFill": {"price": f"{take_profit:.5f}"},
            }
        }
        try:
            resp = httpx.post(
                f"{OANDA_PRACTICE}/v3/accounts/{raw['account_id']}/orders",
                headers={"Authorization": f"Bearer {raw['token']}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            ref = (
                data.get("orderFillTransaction", {}).get("id")
                or data.get("orderCreateTransaction", {}).get("id")
            )
            return {"venue": "demo", "broker_ref": ref}
        except Exception as e:  # noqa: BLE001 — broker errors fall back to paper
            return {"venue": "simulated", "reason": f"demo broker error: {e}"}

    return {"venue": "simulated"}
