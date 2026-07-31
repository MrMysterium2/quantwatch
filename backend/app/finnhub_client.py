import logging
import os
from datetime import date, timedelta
from typing import Optional

import requests

logger = logging.getLogger("quantwatch")

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")


def _is_us_ticker(ticker: str) -> bool:
    return "." not in ticker


def get_company_news(ticker: str, days_back: int = 7) -> list:
    if not FINNHUB_API_KEY or not _is_us_ticker(ticker):
        return []

    today = date.today()
    from_date = today - timedelta(days=days_back)

    try:
        response = requests.get(
            f"{FINNHUB_BASE_URL}/company-news",
            params={
                "symbol": ticker,
                "from": from_date.isoformat(),
                "to": today.isoformat(),
                "token": FINNHUB_API_KEY,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        logger.warning("Finnhub company-news nicht verfuegbar fuer %s (HTTP %s)", ticker, status)
        return []
    except requests.exceptions.RequestException as exc:
        logger.warning("Finnhub company-news Anfrage fehlgeschlagen fuer %s: %s", ticker, exc)
        return []

    return response.json() or []


def get_upcoming_earnings(ticker: str, days_ahead: int = 90) -> Optional[dict]:
    if not FINNHUB_API_KEY or not _is_us_ticker(ticker):
        return None

    today = date.today()
    to_date = today + timedelta(days=days_ahead)

    try:
        response = requests.get(
            f"{FINNHUB_BASE_URL}/calendar/earnings",
            params={
                "symbol": ticker,
                "from": today.isoformat(),
                "to": to_date.isoformat(),
                "token": FINNHUB_API_KEY,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        logger.warning("Finnhub earnings-calendar nicht verfuegbar fuer %s (HTTP %s)", ticker, status)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("Finnhub earnings-calendar Anfrage fehlgeschlagen fuer %s: %s", ticker, exc)
        return None

    data = response.json()
    entries = data.get("earningsCalendar", [])
    if not entries:
        return None

    next_entry = entries[0]
    return {
        "date": next_entry.get("date"),
        "quarter": next_entry.get("quarter"),
        "year": next_entry.get("year"),
        "eps_estimate": next_entry.get("epsEstimate"),
        "revenue_estimate": next_entry.get("revenueEstimate"),
    }
