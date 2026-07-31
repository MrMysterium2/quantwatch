import logging
import math
from datetime import date, datetime
from typing import Optional

import numpy as np
import yfinance as yf

from finnhub_client import get_company_news, get_upcoming_earnings
from market_data import get_snapshot
from models import Empfehlung
from sentiment import aggregate_sentiment

logger = logging.getLogger("quantwatch")


def _clean(value):
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _get_price_history(ticker: str):
    hist = yf.Ticker(ticker).history(period="1y")
    if hist.empty:
        raise ValueError(f"Keine Kurshistorie für '{ticker}' verfügbar")
    return hist


def _compute_rsi(closes, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = closes.diff().dropna()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.rolling(period).mean().iloc[-1]
    avg_loss = losses.rolling(period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_technical(hist) -> dict:
    closes = hist["Close"]
    current_price = closes.iloc[-1]
    sma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else None
    sma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None
    rsi = _compute_rsi(closes)

    trend_component = 0.0
    if sma50 is not None and sma200 is not None:
        if current_price > sma50 > sma200:
            trend_component = 1.0
        elif current_price < sma50 < sma200:
            trend_component = -1.0
        elif current_price > sma50:
            trend_component = 0.4
        else:
            trend_component = -0.4
    elif sma50 is not None:
        trend_component = 0.5 if current_price > sma50 else -0.5

    rsi_component = 0.0
    if rsi is not None:
        if rsi < 30:
            rsi_component = 0.5
        elif rsi > 70:
            rsi_component = -0.5
        else:
            rsi_component = (50 - rsi) / 40

    technical_score = max(-1.0, min(1.0, 0.85 * trend_component + 0.15 * rsi_component))
    technical_score = float(technical_score)

    return {
        "score": _clean(round(technical_score, 3)),
        "current_price": _clean(round(float(current_price), 2)),
        "sma50": _clean(round(float(sma50), 2)) if sma50 is not None else None,
        "sma200": _clean(round(float(sma200), 2)) if sma200 is not None else None,
        "rsi": _clean(round(float(rsi), 1)) if rsi is not None else None,
    }


def _compute_fundamental(snapshot: dict) -> dict:
    trailing_pe = snapshot.get("pe_ratio")
    forward_pe = snapshot.get("forward_pe")

    if not trailing_pe or not forward_pe or trailing_pe <= 0:
        return {"score": 0.0, "note": "KGV-Daten unvollständig, neutral gewertet"}

    growth_signal = (trailing_pe - forward_pe) / trailing_pe
    fundamental_score = max(-1.0, min(1.0, growth_signal / 0.5))

    return {
        "score": _clean(round(fundamental_score, 3)) or 0.0,
        "trailing_pe": _clean(trailing_pe),
        "forward_pe": _clean(forward_pe),
    }


def _compute_risk(hist, beta: Optional[float], days_to_earnings: Optional[int]) -> dict:
    closes = hist["Close"]
    daily_returns = closes.pct_change().dropna()
    volatility = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0.0

    risk_score = volatility * 100

    if beta is not None:
        risk_score += abs(beta - 1.0) * 15

    if days_to_earnings is not None and days_to_earnings <= 7:
        risk_score += 10

    risk_score = max(0.0, min(100.0, risk_score))

    return {
        "score": _clean(round(risk_score, 1)) or 0.0,
        "annualized_volatility_pct": _clean(round(volatility * 100, 1)),
        "beta": _clean(beta),
    }


def generate_recommendation(ticker: str, previous_recommendation: Optional[str] = None) -> dict:
    ticker = ticker.strip().upper()

    snapshot = get_snapshot(ticker)
    hist = _get_price_history(ticker)

    technical = _compute_technical(hist)
    fundamental = _compute_fundamental(snapshot)

    finnhub_symbol = snapshot.get("symbol") or ticker

    earnings = get_upcoming_earnings(finnhub_symbol)
    days_to_earnings = None
    if earnings and earnings.get("date"):
        earnings_date = datetime.strptime(earnings["date"], "%Y-%m-%d").date()
        days_to_earnings = (earnings_date - date.today()).days

    risk = _compute_risk(hist, snapshot.get("beta"), days_to_earnings)

    articles = get_company_news(finnhub_symbol)
    sentiment = aggregate_sentiment(articles) if articles else None
    sentiment_score = sentiment["score"] if sentiment and sentiment.get("score") is not None else None

    if sentiment_score is not None:
        weights = {"technical": 0.40, "fundamental": 0.35, "sentiment": 0.25}
        total_score = (
            weights["technical"] * technical["score"]
            + weights["fundamental"] * fundamental["score"]
            + weights["sentiment"] * sentiment_score
        )
    else:
        weights = {"technical": 0.55, "fundamental": 0.45}
        total_score = (
            weights["technical"] * technical["score"]
            + weights["fundamental"] * fundamental["score"]
        )

    total_score = max(-1.0, min(1.0, total_score))
    total_score = _clean(float(total_score)) or 0.0

    RECOMMENDATION_THRESHOLD = 0.35

    # Hysterese gegen "Flackern" bei Grenzfaellen: der EINSTIEG in Kaufen/Verkaufen bleibt
    # bei der vollen Schwelle (0.35) - sofortige Reaktion, keine Verzoegerung. Der AUSSTIEG
    # zurueck auf Halten braucht aber einen deutlicheren Rueckgang (Schwelle minus Puffer),
    # damit ein Score, der z.B. zwischen 0.32 und 0.38 hin- und herschwankt, stabil auf
    # "kaufen" bleibt statt jede Stunde zu kippen.
    EXIT_BUFFER = 0.10
    exit_threshold = RECOMMENDATION_THRESHOLD - EXIT_BUFFER

    if previous_recommendation == "kaufen" and total_score > exit_threshold:
        recommendation = Empfehlung.KAUFEN
    elif previous_recommendation == "verkaufen" and total_score < -exit_threshold:
        recommendation = Empfehlung.VERKAUFEN
    elif total_score > RECOMMENDATION_THRESHOLD:
        recommendation = Empfehlung.KAUFEN
    elif total_score < -RECOMMENDATION_THRESHOLD:
        recommendation = Empfehlung.VERKAUFEN
    else:
        recommendation = Empfehlung.HALTEN

    expected_return_pct = float(round(total_score * 15, 1))

    def _fmt(value):
        return "n/a" if value is None else value

    reasoning_parts = [
        f"Trend: SMA50={_fmt(technical['sma50'])}, SMA200={_fmt(technical['sma200'])}, RSI={_fmt(technical['rsi'])}",
        f"KGV-Wachstumssignal: {fundamental['score']}",
    ]
    if sentiment_score is not None:
        reasoning_parts.append(f"News-Sentiment: {sentiment_score} ({sentiment['article_count']} Artikel)")
    if days_to_earnings is not None:
        reasoning_parts.append(f"Earnings in {days_to_earnings} Tagen")
    reasoning = " | ".join(reasoning_parts)

    return {
        "ticker": ticker,
        "name": snapshot.get("name"),
        "sector": snapshot.get("sector"),
        "symbol": snapshot.get("symbol"),
        "exchange": snapshot.get("exchange"),
        "recommendation": recommendation.value,
        "expected_return_pct": _clean(expected_return_pct) or 0.0,
        "risk_score": risk["score"],
        "technical_score": _clean(technical["score"]) or 0.0,
        "fundamental_score": _clean(fundamental["score"]) or 0.0,
        "sentiment_score": _clean(sentiment_score),
        "reasoning": reasoning,
        "details": {
            "technical": technical,
            "fundamental": fundamental,
            "risk": risk,
            "sentiment": sentiment,
            "upcoming_earnings": earnings,
            "days_to_earnings": days_to_earnings,
        },
    }
