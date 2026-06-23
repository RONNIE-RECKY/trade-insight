"""Subscription packages and a SIMULATED checkout.

There is no real payment processor wired here — `subscribe` simply records the
chosen plan against the user. Pricing mirrors common market tiers so the
packages UI is realistic, but nothing charges a card. A real processor
(e.g. Stripe) can replace `subscribe` later without changing the gating model.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
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
    """Resolve a user's plan from the DB; unauthenticated/unknown -> free."""
    if user_id is None:
        return "free"
    with db_session() as conn:
        row = conn.execute("SELECT plan FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["plan"] if row else "free"


class SubscribeRequest(BaseModel):
    user_id: int
    plan: str


@router.get("/plans")
def list_plans():
    return {"plans": list(PLANS.values())}


@router.post("/subscribe")
def subscribe(req: SubscribeRequest):
    if req.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"unknown plan '{req.plan}'")
    with db_session() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (req.user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (req.plan, req.user_id))
    # NOTE: simulated — no payment is taken.
    return {"ok": True, "plan": req.plan, "simulated": True}
