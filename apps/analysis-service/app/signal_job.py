"""Signal generation across every tracked symbol and every timeframe
(5min → 1day). This produces a healthy number of trade ideas per day —
not by lowering quality bars, but because each (symbol, timeframe) pair is
its own independent setup. Every signal carries:

  - its OWN backtested hit-rate (real walk-forward replay on that timeframe),
  - explicit entry / stop-loss / take-profit levels (ATR + swing based),
  - a tier: "premium" when the higher timeframes agree AND news doesn't
    contradict (the stricter, higher-conviction subset), else "standard".

No hit-rate is faked or inflated — a noisier 5min setup will simply show a
lower backtested hit-rate than a clean daily one, and the UI surfaces that.
"""
from __future__ import annotations

import json
from datetime import date

from .backtest import run_backtest
from .commentary import generate_analysis_commentary, generate_signal_commentary
from .data_feed import get_candles
from .db import db_session
from .fixtures import SYMBOLS
from .indicators import compute_indicators, latest_indicator_signals
from .market_context import current_position
from .news import get_news_sentiment
from .patterns import detect_all_patterns, detect_patterns
from .strategies import evaluate_strategies
from .trade_levels import compute_trade_levels

# Every timeframe we predict on (1-minute deliberately excluded — too noisy).
PREDICTION_TIMEFRAMES = ["5min", "15min", "30min", "1h", "4h", "1day"]
# Higher timeframes used for the premium multi-timeframe agreement gate.
HIGHER_TIMEFRAMES = ["1h", "4h", "1day"]
# Minimum confluence for a setup to be published as a signal at all. We keep
# this low so the feed has useful breadth across symbols/timeframes; quality is
# communicated per-signal via the tier ("premium" = multi-timeframe agreement)
# and each signal's own real backtested hit-rate — not by hiding weaker setups.
MIN_CONFLUENCE = 1
# A setup is only labelled "high confidence" when its MEASURED backtested
# hit-rate clears this bar (plus strong strategy agreement). Never a claim.
HIGH_CONFIDENCE_TARGET = 0.80


def analyze_symbol(symbol: str, interval: str = "1day") -> dict:
    df = get_candles(symbol, interval=interval, count=300)
    enriched = compute_indicators(df)
    ind_signals = latest_indicator_signals(enriched)
    pats = detect_patterns(df)
    result = evaluate_strategies(ind_signals, pats)
    result["indicator_signals"] = ind_signals
    result["patterns"] = pats
    result["symbol"] = symbol
    result["interval"] = interval
    result["candle_count"] = len(df)
    last = enriched.iloc[-1] if len(enriched) else None
    result["close"] = float(last["close"]) if last is not None else None
    result["atr"] = float(last["atr_14"]) if last is not None and last.get("atr_14") == last.get("atr_14") else None
    result["last_ts"] = str(last["ts"]) if last is not None else None
    return result


def analyze_symbol_multi_timeframe(symbol: str) -> dict:
    per_tf = {tf: analyze_symbol(symbol, interval=tf) for tf in HIGHER_TIMEFRAMES}

    directions = [r["direction"] for r in per_tf.values() if r["direction"] != "neutral"]
    if directions and all(d == directions[0] for d in directions) and len(directions) == len(HIGHER_TIMEFRAMES):
        agreed_direction = directions[0]
    else:
        agreed_direction = "neutral"

    return {
        "symbol": symbol,
        "direction": agreed_direction,
        "timeframes": per_tf,
        "all_agree": agreed_direction != "neutral",
    }


def full_analysis(symbol: str, interval: str) -> dict:
    """On-demand, whole-graph analysis for a user-chosen timeframe: every chart
    pattern across the series, the trade plan (entry/SL/TP), the current price
    position within that structure, the news read and a plain-English summary."""
    df = get_candles(symbol, interval=interval, count=300)
    enriched = compute_indicators(df)
    ind_signals = latest_indicator_signals(enriched)

    # whole-graph patterns (every double top/bottom + strongest S/R zones),
    # scored with the same latest-bar pattern read used elsewhere
    all_patterns = detect_all_patterns(df)
    scoring_patterns = detect_patterns(df)
    result = evaluate_strategies(ind_signals, scoring_patterns)

    last = enriched.iloc[-1] if len(enriched) else None
    close = float(last["close"]) if last is not None else None
    atr = float(last["atr_14"]) if last is not None and last.get("atr_14") == last.get("atr_14") else None

    levels = compute_trade_levels(result["direction"], close, atr, scoring_patterns)
    position = current_position(df, enriched, levels)
    news = get_news_sentiment(symbol)
    commentary = generate_analysis_commentary(
        symbol, interval, result["direction"], result["factors"], position, news
    )

    # Confidence is EARNED, not claimed: we measure this exact rule's real
    # walk-forward hit-rate and only call it "high" when that measured number
    # clears the target AND the strategies strongly agree AND news doesn't fight
    # the direction. Otherwise it's labelled medium/low honestly.
    bt = run_backtest(df)
    hit_rate = bt["hit_rate"]
    agree_count = result["confluence_score"]
    news_ok = news["sentiment"] in ("neutral", result["direction"])
    meets_target = hit_rate is not None and hit_rate >= HIGH_CONFIDENCE_TARGET
    high_confidence = bool(
        result["direction"] != "neutral" and meets_target and agree_count >= 4 and news_ok
    )
    if high_confidence:
        confidence = "high"
    elif result["direction"] != "neutral" and agree_count >= 3 and (hit_rate or 0) >= 0.6:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "symbol": symbol,
        "interval": interval,
        "direction": result["direction"],
        "confluence_score": result["confluence_score"],
        "factors": result["factors"],
        "strategies": result["strategies"],
        "strategy_agreement": result["strategy_agreement"],
        "indicator_signals": ind_signals,
        "patterns": all_patterns,
        "levels": levels,
        "current_position": position,
        "news_sentiment": news["sentiment"],
        "news_headlines": news["headlines"],
        "commentary": commentary,
        "backtest_hit_rate": hit_rate,
        "backtest_sample_size": bt["total_signals"],
        "confidence": confidence,
        "high_confidence": high_confidence,
        "meets_target": meets_target,
        "target_accuracy": HIGH_CONFIDENCE_TARGET,
        "candle_count": len(df),
    }


def predict_symbol_timeframes(symbol: str) -> list[dict]:
    """Per-timeframe trade predictions for one symbol, with levels (no DB write).
    Used by the /predictions/{symbol} endpoint and the daily scan."""
    news = get_news_sentiment(symbol)
    mtf = _mtf_from_higher(symbol)

    predictions = []
    for tf in PREDICTION_TIMEFRAMES:
        analysis = analyze_symbol(symbol, tf)
        levels = compute_trade_levels(analysis["direction"], analysis["close"], analysis["atr"], analysis["patterns"])
        tier = _tier(tf, analysis["direction"], mtf, news)
        predictions.append(
            {
                "symbol": symbol,
                "interval": tf,
                "direction": analysis["direction"],
                "confluence_score": analysis["confluence_score"],
                "factors": analysis["factors"],
                "patterns": analysis["patterns"],
                "indicator_signals": analysis["indicator_signals"],
                "levels": levels,
                "tier": tier,
                "news_sentiment": news["sentiment"],
            }
        )
    return predictions


def _mtf_from_higher(symbol: str) -> dict:
    """Lightweight MTF check reusing higher-timeframe analyses."""
    return analyze_symbol_multi_timeframe(symbol)


def _tier(tf: str, direction: str, mtf: dict, news: dict) -> str:
    news_ok = news["sentiment"] == "neutral" or news["sentiment"] == direction
    if (
        tf in HIGHER_TIMEFRAMES
        and mtf["all_agree"]
        and direction == mtf["direction"]
        and news_ok
    ):
        return "premium"
    return "standard"


def run_daily_signal_scan(symbols: list[str] | None = None) -> list[dict]:
    symbols = symbols or SYMBOLS
    today = date.today().isoformat()

    # regenerate today's signals from scratch so re-running is idempotent
    with db_session() as conn:
        conn.execute("DELETE FROM signals WHERE date = ?", (today,))

    stored = []
    for symbol in symbols:
        news = get_news_sentiment(symbol)
        mtf = _mtf_from_higher(symbol)

        for tf in PREDICTION_TIMEFRAMES:
            analysis = analyze_symbol(symbol, tf)
            if analysis["direction"] == "neutral" or analysis["confluence_score"] < MIN_CONFLUENCE:
                continue

            levels = compute_trade_levels(analysis["direction"], analysis["close"], analysis["atr"], analysis["patterns"])
            if levels is None:
                continue

            tier = _tier(tf, analysis["direction"], mtf, news)
            df = get_candles(symbol, interval=tf, count=300, refresh=False)
            bt = run_backtest(df)
            commentary = generate_signal_commentary(symbol, tf, analysis["direction"], analysis["factors"], tier, news)

            with db_session() as conn:
                cur = conn.execute(
                    "INSERT INTO signals (symbol, date, direction, confluence_score, reasoning_json, "
                    "backtest_hit_rate, timeframes_agreed, news_sentiment, interval, tier, "
                    "entry, stop_loss, take_profit, risk_reward) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        symbol,
                        today,
                        analysis["direction"],
                        analysis["confluence_score"],
                        json.dumps(
                            {
                                "factors": analysis["factors"],
                                "indicator_signals": analysis["indicator_signals"],
                                "patterns": analysis["patterns"],
                                "strategies": analysis.get("strategies", []),
                                "strategy_agreement": analysis.get("strategy_agreement"),
                                "commentary": commentary,
                                "news_headlines": news["headlines"],
                            }
                        ),
                        bt["hit_rate"],
                        json.dumps(list(HIGHER_TIMEFRAMES)) if tier == "premium" else None,
                        news["sentiment"],
                        tf,
                        tier,
                        levels["entry"],
                        levels["stop_loss"],
                        levels["take_profit"],
                        levels["risk_reward"],
                    ),
                )
                stored.append({"id": cur.lastrowid, "symbol": symbol, "interval": tf, "tier": tier})

    return get_today_signal()


def get_today_signal() -> list[dict]:
    today = date.today().isoformat()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE date = ? "
            "ORDER BY CASE tier WHEN 'premium' THEN 0 ELSE 1 END, confluence_score DESC",
            (today,),
        ).fetchall()
    return [_row_to_signal(r) for r in rows]


def get_signal_of_the_day() -> dict | None:
    """The single best setup across every symbol AND timeframe scanned today.

    "Best" is a transparent composite — not a separate hidden model — of the
    same honest signals already on the platform:
      - the signal's OWN backtested hit-rate (50% weight, the dominant factor),
      - whether it cleared the "premium" bar (multi-timeframe agreement + news
        not contradicting, 25%),
      - how many strategies agreed (confluence, 15%),
      - the adaptive learning weight of the strategies that voted its direction
        (10%) — strategies with a real track record of being right count for
        a bit more, same mechanism as learning.py's auto-trade re-weighting.
    No timeframe is preferred over another; a clean 5-minute setup can win
    over a noisy daily one if its real numbers are better.
    """
    signals = get_today_signal()
    if not signals:
        signals = run_daily_signal_scan()

    candidates = [s for s in signals if s["direction"] != "neutral" and s.get("entry") is not None]
    if not candidates:
        return None

    from .learning import get_weights

    weights = get_weights()

    def strategy_weight_avg(sig: dict) -> float:
        strategies = sig.get("reasoning", {}).get("strategies", [])
        agreeing = [st for st in strategies if st.get("signal") == sig["direction"]]
        if not agreeing:
            return 1.0
        vals = [weights.get(st["name"], 1.0) for st in agreeing]
        return sum(vals) / len(vals)

    def score(sig: dict) -> float:
        hit = sig.get("backtest_hit_rate") or 0.0
        tier_bonus = 1.0 if sig.get("tier") == "premium" else 0.0
        confluence = min(sig.get("confluence_score", 0), 6) / 6
        learned = strategy_weight_avg(sig) / 1.8  # normalised against learning.py's max weight
        return hit * 0.5 + tier_bonus * 0.25 + confluence * 0.15 + learned * 0.10

    best = max(candidates, key=score)
    best = dict(best)
    best["composite_score"] = round(score(best), 4)
    return best


def get_signal_history(limit: int = 60) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY date DESC, "
            "CASE tier WHEN 'premium' THEN 0 ELSE 1 END, confluence_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_signal(r) for r in rows]


def _row_to_signal(row) -> dict:
    d = dict(row)
    d["reasoning"] = json.loads(d.pop("reasoning_json"))
    if d.get("timeframes_agreed"):
        d["timeframes_agreed"] = json.loads(d["timeframes_agreed"])
    return d
