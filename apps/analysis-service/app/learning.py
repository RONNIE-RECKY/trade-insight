"""Adaptive strategy learning.

This is an honest, measurable form of "the AI learns": as the bot's paper
trades close (win/loss), we credit the strategies that voted in the winning
direction and debit those that didn't. Each strategy's running win-rate sets
the WEIGHT it carries in future consensus decisions — so strategies that have
actually been working count for more, and weak ones fade. It does not invent
new strategies; it re-weights the existing ones from real outcomes.

Weights start at 1.0 (neutral) and only move once there's enough sample size,
so early behaviour is unchanged and the system improves with usage.
"""
from __future__ import annotations

import json

from .db import db_session

_MIN_SAMPLES = 8        # need this many graded trades before a weight moves
_MIN_W, _MAX_W = 0.4, 1.8


def get_weights() -> dict[str, float]:
    with db_session() as conn:
        rows = conn.execute("SELECT name, weight FROM strategy_weights").fetchall()
    return {r["name"]: r["weight"] for r in rows}


def _recompute_weight(wins: int, total: int) -> float:
    if total < _MIN_SAMPLES:
        return 1.0
    rate = wins / total  # 0..1
    # map a 50% win-rate to weight 1.0, scale around it, then clamp
    w = 0.5 + rate  # 0.5..1.5
    return max(_MIN_W, min(_MAX_W, round(w, 3)))


def apply_outcomes() -> dict:
    """Feed any newly-closed paper trades into the strategy weights."""
    with db_session() as conn:
        trades = conn.execute(
            "SELECT t.id, t.direction, t.outcome, t.signal_id, s.reasoning_json "
            "FROM auto_trades t LEFT JOIN signals s ON s.id = t.signal_id "
            "WHERE t.status='closed' AND t.learned=0"
        ).fetchall()

    graded = 0
    for t in trades:
        won = t["outcome"] == "win"
        strategies = []
        if t["reasoning_json"]:
            try:
                strategies = json.loads(t["reasoning_json"]).get("strategies", [])
            except Exception:
                strategies = []
        with db_session() as conn:
            for st in strategies:
                # a strategy is "credited" when it voted the trade's direction
                if st.get("signal") != t["direction"]:
                    continue
                name = st["name"]
                conn.execute(
                    "INSERT INTO strategy_weights (name, wins, total) VALUES (?, ?, 1) "
                    "ON CONFLICT(name) DO UPDATE SET wins = wins + ?, total = total + 1, "
                    "updated_at = datetime('now')",
                    (name, 1 if won else 0, 1 if won else 0),
                )
            conn.execute("UPDATE auto_trades SET learned=1 WHERE id=?", (t["id"],))
        graded += 1

    # recompute weights from the updated tallies
    with db_session() as conn:
        rows = conn.execute("SELECT name, wins, total FROM strategy_weights").fetchall()
        for r in rows:
            conn.execute(
                "UPDATE strategy_weights SET weight=? WHERE name=?",
                (_recompute_weight(r["wins"], r["total"]), r["name"]),
            )
    return {"graded_trades": graded}


def stats() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT name, wins, total, weight FROM strategy_weights ORDER BY weight DESC"
        ).fetchall()
    return [dict(r) for r in rows]
