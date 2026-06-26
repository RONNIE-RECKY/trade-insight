"""Subscription packages and a SIMULATED checkout.

There is no real payment processor wired here — `subscribe` simply records the
chosen plan against the user. Pricing mirrors common market tiers so the
packages UI is realistic, but nothing charges a card. A real processor
(e.g. Stripe) can replace `subscribe` later without changing the gating model.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .db import db_session

router = APIRouter(prefix="/billing")

# Ordered weakest → strongest. `rank` drives feature gating; each tier is a
# strict superset of the one below it (see `capabilities`).
PLANS = {
    "free": {
        "id": "free",
        "name": "Free",
        "price": 0,
        "rank": 0,
        "tagline": "Try it on gold",
        "highlight": "1 gold signal a day",
        "features": [
            "1 daily signal — XAU/USD (gold) only",
            "Daily-timeframe chart read",
            "See entry, stop & target on that signal",
        ],
        "capabilities": {
            "max_daily_signals": 1,
            "timeframes": ["1day"],
            "locked_symbols": ["XAUUSD"],   # free is locked to gold only
            "premium_signals": False,
            "intraday_bot": False,
            "export": False,
            "watchlist_limit": 1,
            "api_access": False,
            "auto_trade": False,
        },
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price": 49.99,
        "rank": 1,
        "tagline": "For active traders",
        "highlight": "Up to 10 signals/day",
        "features": [
            "Everything in Free, plus:",
            "Up to 10 signals per day, all 10 markets",
            "All timeframes (5M–1D) bot analysis",
            "Entry / stop / take-profit on every setup",
            "Export analysis & patterns (CSV/JSON)",
            "Unlimited watchlist",
        ],
        "capabilities": {
            "max_daily_signals": 10,
            "timeframes": ["5min", "15min", "30min", "1h", "4h", "1day"],
            "locked_symbols": None,
            "premium_signals": False,
            "intraday_bot": True,
            "export": True,
            "watchlist_limit": None,
            "api_access": False,
            "auto_trade": False,
        },
    },
    "ultimate": {
        "id": "ultimate",
        "name": "Ultimate",
        "price": 99.99,
        "rank": 2,
        "popular": True,
        "tagline": "Most popular",
        "highlight": "Up to 40 signals/day + premium",
        "features": [
            "Everything in Pro, plus:",
            "Up to 40 signals per day",
            "Premium multi-timeframe signals",
            "High-confidence (80%+ backtested) highlights",
            "6-strategy consensus + news filtering",
            "Automated bot — connect a demo account for live execution",
            "Full backtest history per rule",
        ],
        "capabilities": {
            "max_daily_signals": 40,
            "timeframes": ["5min", "15min", "30min", "1h", "4h", "1day"],
            "locked_symbols": None,
            "premium_signals": True,
            "intraday_bot": True,
            "export": True,
            "watchlist_limit": None,
            "api_access": False,
            "auto_trade": True,
        },
    },
    "platinum": {
        "id": "platinum",
        "name": "Platinum",
        "price": 299.99,
        "rank": 3,
        "tagline": "For professionals",
        "highlight": "Unlimited + API",
        "features": [
            "Everything in Ultimate, plus:",
            "Unlimited signals, all markets, priority scans",
            "Automated paper-trading bot — unlimited positions",
            "Programmatic API access to signals & exports",
            "Early access to new strategies",
            "Priority support",
        ],
        "capabilities": {
            "max_daily_signals": None,   # unlimited
            "timeframes": ["5min", "15min", "30min", "1h", "4h", "1day"],
            "locked_symbols": None,
            "premium_signals": True,
            "intraday_bot": True,
            "export": True,
            "watchlist_limit": None,
            "api_access": True,
            "auto_trade": True,
        },
    },
}


def capabilities(plan: str) -> dict:
    return PLANS.get(plan, PLANS["free"])["capabilities"]


def user_plan(user_id: int | None) -> str:
    """Resolve a user's plan from the DB; unauthenticated/unknown -> free.
    Admins always get full (platinum) access regardless of stored plan."""
    if user_id is None:
        return "free"
    with db_session() as conn:
        row = conn.execute("SELECT plan, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return "free"
    return "platinum" if row["is_admin"] else row["plan"]


import os

from fastapi import Header

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:3000")


class SubscribeRequest(BaseModel):
    user_id: int
    plan: str


class CheckoutRequest(BaseModel):
    user_id: int
    plan: str


def _is_admin(user_id: int | None) -> bool:
    if user_id is None:
        return False
    with db_session() as conn:
        row = conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["is_admin"])


def _set_plan(user_id: int, plan: str) -> None:
    with db_session() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))


@router.get("/plans")
def list_plans():
    return {"plans": list(PLANS.values()), "payments_enabled": bool(STRIPE_SECRET_KEY)}


@router.post("/checkout")
def checkout(req: CheckoutRequest):
    """Start a real paid upgrade. Returns a Stripe Checkout URL. The plan is only
    granted by the webhook AFTER payment — never client-side. Closes the loophole
    where anyone could switch plans for free."""
    plan = PLANS.get(req.plan)
    if not plan or req.plan == "free":
        raise HTTPException(status_code=400, detail="pick a paid plan")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="payments are not configured yet")
    try:
        import stripe

        stripe.api_key = STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "recurring": {"interval": "month"},
                    "product_data": {"name": f"PIP HIVE {plan['name']}"},
                    "unit_amount": int(plan["price"] * 100),
                },
                "quantity": 1,
            }],
            metadata={"user_id": str(req.user_id), "plan": req.plan},
            success_url=f"{WEB_BASE_URL}/account?upgraded=1",
            cancel_url=f"{WEB_BASE_URL}/pricing",
        )
        return {"url": session.url}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"checkout error: {e}")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe calls this after a successful payment; only here is a plan granted."""
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="webhook not configured")
    import stripe

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid webhook: {e}")

    if event["type"] == "checkout.session.completed":
        md = event["data"]["object"].get("metadata") or {}
        uid, plan = md.get("user_id"), md.get("plan")
        if uid and plan in PLANS:
            _set_plan(int(uid), plan)
    return {"received": True}


@router.post("/subscribe")
def subscribe(req: SubscribeRequest, x_user_id: int | None = Header(default=None)):
    """Admin-only manual plan grant (support / testing). Normal users must pay
    via /checkout — this endpoint no longer lets anyone self-assign a plan."""
    if not _is_admin(x_user_id):
        raise HTTPException(status_code=403, detail="plan changes require payment via checkout")
    if req.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"unknown plan '{req.plan}'")
    _set_plan(req.user_id, req.plan)
    return {"ok": True, "plan": req.plan, "by_admin": True}
