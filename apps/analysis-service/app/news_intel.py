"""News Intel — event-driven prediction for XAU/USD (gold).

Gold reacts sharply to scheduled US macro releases (NFP, CPI, FOMC rate
decisions, jobless claims, etc.). On each such event this module re-runs the
platform's full analysis engine on XAU/USD and publishes a prediction:
direction, an honest probability, and a trade plan (entry/SL/TP).

HONESTY (the whole point of this platform, see the project plan):
  - The "probability" is NOT a made-up marketing accuracy. It's a transparent
    composite dominated by this exact setup's REAL walk-forward backtested
    hit-rate (from backtest.py), nudged by how many strategies agree and
    whether the news read aligns. If there isn't enough backtest history, we
    say so and show no number rather than invent one.
  - Every prediction is STORED and later GRADED against the actual price move
    after the event (grade_due_predictions). Over time this produces a real,
    verifiable track record — the opposite of an unverifiable "98.7%" claim.

Live economic calendar comes from Finnhub when FINNHUB_API_KEY is set; without
it we fall back to a deterministic recurring schedule of the events we can
compute reliably (NFP = first Friday, weekly jobless claims = Thursdays, plus a
small known FOMC/CPI list), each clearly flagged as an approximate schedule.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone

import httpx

from .data_feed import get_live_price
from .db import db_session
from .signal_job import full_analysis

SYMBOL = "XAUUSD"
# Timeframe we analyse for an event read — 1h balances reactivity to the
# release with enough structure to be meaningful.
EVENT_TIMEFRAME = "1h"

# High-impact, gold-relevant US releases. `impact` drives how prominently the
# UI surfaces it; `move_pct` is the historical rough post-event move band for
# gold, used only to size the outcome-grading window (never shown as a claim).
GOLD_EVENTS = {
    "NFP": {"name": "US Non-Farm Payrolls", "impact": "high"},
    "CPI": {"name": "US CPI (inflation)", "impact": "high"},
    "FOMC": {"name": "FOMC rate decision", "impact": "high"},
    "PPI": {"name": "US PPI", "impact": "medium"},
    "GDP": {"name": "US GDP", "impact": "medium"},
    "RETAIL": {"name": "US retail sales", "impact": "medium"},
    "CLAIMS": {"name": "US initial jobless claims", "impact": "medium"},
    "POWELL": {"name": "Fed Chair Powell speaks", "impact": "high"},
}

# Known FOMC decision dates (approx, extend as needed). Used only in the
# fixture path when there's no live calendar key.
_KNOWN_FOMC_DATES = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]
# Approx CPI release days per month (fixture path only).
_KNOWN_CPI_DATES_2026 = {
    1: 13, 2: 11, 3: 11, 4: 10, 5: 12, 6: 10,
    7: 14, 8: 12, 9: 11, 10: 13, 11: 12, 12: 10,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _first_friday(year: int, month: int) -> datetime:
    d = datetime(year, month, 1, 13, 30, tzinfo=timezone.utc)  # 08:30 ET ≈ 13:30 UTC
    # weekday(): Mon=0 .. Fri=4
    offset = (4 - d.weekday()) % 7
    return d + timedelta(days=offset)


def _fixture_events(window_start: datetime, window_end: datetime) -> list[dict]:
    """Deterministic recurring schedule of computable gold events in the window.
    Clearly flagged approximate — real times come from the live calendar."""
    events: list[dict] = []

    # iterate each month the window touches
    months = set()
    cur = window_start.replace(day=1)
    while cur <= window_end:
        months.add((cur.year, cur.month))
        # advance one month
        cur = (cur.replace(day=28) + timedelta(days=7)).replace(day=1)

    for (yr, mo) in months:
        # NFP — first Friday 13:30 UTC
        nfp = _first_friday(yr, mo)
        events.append({"code": "NFP", "time": nfp})
        # CPI — known/approx day 13:30 UTC
        cpi_day = _KNOWN_CPI_DATES_2026.get(mo, 12)
        try:
            events.append({"code": "CPI", "time": datetime(yr, mo, cpi_day, 13, 30, tzinfo=timezone.utc)})
        except ValueError:
            pass

    # FOMC — known dates 19:00 UTC (14:00 ET)
    for ds in _KNOWN_FOMC_DATES:
        dt = datetime.fromisoformat(ds).replace(hour=19, tzinfo=timezone.utc)
        events.append({"code": "FOMC", "time": dt})

    # Weekly initial jobless claims — every Thursday 13:30 UTC
    d = window_start
    while d <= window_end:
        if d.weekday() == 3:  # Thursday
            events.append({"code": "CLAIMS", "time": d.replace(hour=13, minute=30, second=0, microsecond=0)})
        d += timedelta(days=1)

    out = []
    for e in events:
        if window_start <= e["time"] <= window_end:
            meta = GOLD_EVENTS[e["code"]]
            out.append(
                {
                    "code": e["code"],
                    "name": meta["name"],
                    "impact": meta["impact"],
                    "time": e["time"].isoformat(),
                    "source": "scheduled (approx)",
                }
            )
    out.sort(key=lambda x: x["time"])
    return out


def _live_events(window_start: datetime, window_end: datetime) -> list[dict]:
    """Finnhub economic calendar, filtered to high/medium-impact US events that
    move gold. Requires FINNHUB_API_KEY."""
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        raise RuntimeError("FINNHUB_API_KEY not set")
    resp = httpx.get(
        "https://finnhub.io/api/v1/calendar/economic",
        params={
            "token": key,
            "from": window_start.date().isoformat(),
            "to": window_end.date().isoformat(),
        },
        timeout=15,
    )
    resp.raise_for_status()
    items = (resp.json() or {}).get("economicCalendar", []) or []

    def classify(evt: str) -> str | None:
        e = evt.lower()
        if "non farm" in e or "nonfarm" in e or "payroll" in e:
            return "NFP"
        if "cpi" in e or "consumer price" in e:
            return "CPI"
        if "fomc" in e or "interest rate" in e or "rate decision" in e:
            return "FOMC"
        if "ppi" in e or "producer price" in e:
            return "PPI"
        if "gdp" in e:
            return "GDP"
        if "retail sales" in e:
            return "RETAIL"
        if "jobless" in e or "initial claims" in e:
            return "CLAIMS"
        if "powell" in e:
            return "POWELL"
        return None

    out = []
    for it in items:
        if (it.get("country") or "").upper() not in ("US", "USD", "UNITED STATES"):
            continue
        code = classify(it.get("event", ""))
        if not code:
            continue
        t = it.get("time") or it.get("date")
        if not t:
            continue
        try:
            dt = datetime.fromisoformat(t.replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if not (window_start <= dt <= window_end):
            continue
        out.append(
            {
                "code": code,
                "name": it.get("event") or GOLD_EVENTS[code]["name"],
                "impact": GOLD_EVENTS[code]["impact"],
                "time": dt.isoformat(),
                "actual": it.get("actual"),
                "estimate": it.get("estimate"),
                "prev": it.get("prev"),
                "source": "live",
            }
        )
    out.sort(key=lambda x: x["time"])
    return out


def get_gold_events(days_back: int = 1, days_ahead: int = 7) -> list[dict]:
    """Gold-relevant macro events from `days_back` ago to `days_ahead` out."""
    start = _now() - timedelta(days=days_back)
    end = _now() + timedelta(days=days_ahead)
    try:
        return _live_events(start, end)
    except Exception:
        return _fixture_events(start, end)


def _probability(analysis: dict) -> float | None:
    """Honest composite probability, DOMINATED by the setup's real backtested
    hit-rate. Returns None when there isn't enough backtest history — we never
    invent a number.

      prob = 0.70 * backtested_hit_rate
           + 0.20 * (strategies agreeing / 11)
           + 0.10 * (news aligns with the direction ? 1 : 0)

    Bounded [0,1], and because the hit-rate term is the dominant one, the
    number can't run away from what actually backtested.
    """
    hit = analysis.get("backtest_hit_rate")
    if hit is None:
        return None
    agreement = min(analysis.get("confluence_score", 0), 11) / 11  # 11-strategy consensus
    news_ok = 1.0 if analysis.get("news_sentiment") in ("neutral", analysis.get("direction")) else 0.0
    prob = 0.70 * hit + 0.20 * agreement + 0.10 * news_ok
    return round(max(0.0, min(1.0, prob)), 4)


def generate_event_intel(event: dict, store: bool = True) -> dict:
    """Run the full XAU/USD engine for one event and build the prediction."""
    analysis = full_analysis(SYMBOL, EVENT_TIMEFRAME)
    prob = _probability(analysis)
    try:
        price_now = get_live_price(SYMBOL)["price"]
    except Exception:
        price_now = analysis.get("current_position", {}).get("current_price")

    intel = {
        "event": event,
        "symbol": SYMBOL,
        "interval": EVENT_TIMEFRAME,
        "direction": analysis["direction"],
        "probability": prob,
        "confidence": analysis.get("confidence"),
        "backtest_hit_rate": analysis.get("backtest_hit_rate"),
        "backtest_sample_size": analysis.get("backtest_sample_size"),
        "confluence_score": analysis.get("confluence_score"),
        "strategy_agreement": analysis.get("strategy_agreement"),
        "strategies": analysis.get("strategies"),
        "news_sentiment": analysis.get("news_sentiment"),
        "news_headlines": analysis.get("news_headlines"),
        "levels": analysis.get("levels"),
        "commentary": analysis.get("commentary"),
        "price_at_prediction": price_now,
        "generated_at": _now().isoformat(),
    }

    if store and analysis["direction"] != "neutral":
        with db_session() as conn:
            conn.execute(
                "INSERT INTO news_intel (event_code, event_name, event_time, symbol, direction, "
                "probability, entry, stop_loss, take_profit, risk_reward, reasoning_json, "
                "price_at_prediction, outcome) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
                (
                    event.get("code"),
                    event.get("name"),
                    event.get("time"),
                    SYMBOL,
                    analysis["direction"],
                    prob,
                    (analysis.get("levels") or {}).get("entry"),
                    (analysis.get("levels") or {}).get("stop_loss"),
                    (analysis.get("levels") or {}).get("take_profit"),
                    (analysis.get("levels") or {}).get("risk_reward"),
                    json.dumps(
                        {
                            "strategies": analysis.get("strategies"),
                            "strategy_agreement": analysis.get("strategy_agreement"),
                            "news_sentiment": analysis.get("news_sentiment"),
                            "commentary": analysis.get("commentary"),
                            "confidence": analysis.get("confidence"),
                        }
                    ),
                    price_now,
                ),
            )
    return intel


def get_news_intel() -> dict:
    """The current News Intel read for gold: the most relevant event (the next
    upcoming one, or the one that just fired) plus the live prediction, and the
    realized track record so far."""
    events = get_gold_events()
    now = _now()

    focus = None
    # prefer an event within +/- 6h of now (the "live" window), else next upcoming
    for e in events:
        et = datetime.fromisoformat(e["time"])
        if abs((et - now).total_seconds()) <= 6 * 3600:
            focus = e
            break
    if focus is None:
        upcoming = [e for e in events if datetime.fromisoformat(e["time"]) >= now]
        focus = upcoming[0] if upcoming else (events[-1] if events else None)

    intel = generate_event_intel(focus, store=False) if focus else None
    return {
        "focus_event": focus,
        "upcoming_events": events,
        "intel": intel,
        "track_record": accuracy_record(),
    }


def grade_due_predictions() -> dict:
    """Grade stored predictions whose event is now >= 4h in the past by
    comparing the current price to the price at prediction time. A prediction
    'hit' if price moved in the predicted direction. Builds the real track
    record shown to users."""
    now = _now()
    graded = 0
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM news_intel WHERE outcome = 'pending'"
        ).fetchall()

    for r in rows:
        try:
            et = datetime.fromisoformat(r["event_time"])
        except (ValueError, TypeError):
            continue
        if (now - et).total_seconds() < 4 * 3600:
            continue  # not enough time has passed to judge the move
        try:
            price_after = get_live_price(SYMBOL)["price"]
        except Exception:
            continue
        p0 = r["price_at_prediction"]
        if p0 is None:
            outcome = "neutral"
        else:
            move = price_after - p0
            if abs(move) < p0 * 0.0005:  # < 0.05% — call it flat
                outcome = "neutral"
            elif (move > 0 and r["direction"] == "bullish") or (move < 0 and r["direction"] == "bearish"):
                outcome = "hit"
            else:
                outcome = "miss"
        with db_session() as conn:
            conn.execute(
                "UPDATE news_intel SET outcome = ?, price_after = ?, graded_at = ? WHERE id = ?",
                (outcome, price_after, now.isoformat(), r["id"]),
            )
        graded += 1
    return {"graded": graded}


def accuracy_record() -> dict:
    """Realized hit-rate of past News Intel predictions — measured, not claimed."""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT outcome, COUNT(*) AS c FROM news_intel WHERE outcome != 'pending' GROUP BY outcome"
        ).fetchall()
    counts = {r["outcome"]: r["c"] for r in rows}
    hits = counts.get("hit", 0)
    misses = counts.get("miss", 0)
    neutral = counts.get("neutral", 0)
    decided = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "neutral": neutral,
        "graded": decided + neutral,
        "hit_rate": round(hits / decided, 4) if decided else None,
    }


def recent_predictions(limit: int = 10) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM news_intel ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("reasoning_json"):
            try:
                d["reasoning"] = json.loads(d.pop("reasoning_json"))
            except Exception:
                d["reasoning"] = {}
        out.append(d)
    return out
