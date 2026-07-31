import logging
import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import yfinance as yf

logger = logging.getLogger("quantwatch")

EVALUATION_HORIZON_DAYS = 14


def _safe(value):
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _price_on_or_after(ticker: str, target_date, cache: dict) -> Optional[float]:
    cache_key = (ticker, target_date)
    if cache_key in cache:
        return cache[cache_key]

    try:
        hist = yf.Ticker(ticker).history(start=target_date, end=target_date + timedelta(days=5))
    except Exception as exc:
        logger.warning("Backtest: Kursabfrage fuer %s fehlgeschlagen: %s", ticker, exc)
        cache[cache_key] = None
        return None

    if hist.empty:
        cache[cache_key] = None
        return None

    price = _safe(float(hist["Close"].iloc[0]))
    cache[cache_key] = price
    return price


def evaluate_score(score, cache: dict) -> Optional[dict]:
    created = score.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    target_date = created + timedelta(days=EVALUATION_HORIZON_DAYS)
    if datetime.now(timezone.utc) < target_date:
        return None

    price_then = _price_on_or_after(score.ticker, created.date(), cache)
    price_after = _price_on_or_after(score.ticker, target_date.date(), cache)

    if price_then is None or price_after is None or price_then == 0:
        return None

    actual_return_pct = _safe(round((price_after - price_then) / price_then * 100, 2))
    if actual_return_pct is None:
        return None

    direction_correct = None
    if score.recommendation.value == "kaufen":
        direction_correct = actual_return_pct > 0
    elif score.recommendation.value == "verkaufen":
        direction_correct = actual_return_pct < 0

    return {
        "ticker": score.ticker,
        "scored_at": score.created_at.isoformat(),
        "recommendation": score.recommendation.value,
        "expected_return_pct": _safe(score.expected_return_pct),
        "actual_return_pct": actual_return_pct,
        "direction_correct": direction_correct,
        "had_sentiment": score.sentiment_score is not None,
    }


def run_backtest(scores: List) -> dict:
    price_cache: dict = {}
    evaluated = []
    for score in scores:
        try:
            result = evaluate_score(score, price_cache)
        except Exception as exc:
            logger.warning("Backtest: Auswertung fuer %s fehlgeschlagen: %s", score.ticker, exc)
            continue
        if result is not None:
            evaluated.append(result)

    directional_results = [e for e in evaluated if e["direction_correct"] is not None]
    hit_rate = None
    if directional_results:
        hits = sum(1 for e in directional_results if e["direction_correct"])
        hit_rate = round(hits / len(directional_results) * 100, 1)

    return {
        "evaluated_count": len(evaluated),
        "hit_rate_pct": hit_rate,
        "details": evaluated,
    }
