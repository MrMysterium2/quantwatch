import math
import re
from datetime import datetime
from typing import Optional

import yfinance as yf

PERIOD_INTERVALS = {
    "1d": "5m",
    "5d": "15m",
    "1mo": "1d",
    "6mo": "1d",
    "ytd": "1d",
    "1y": "1d",
    "5y": "1wk",
}

_ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def _is_isin(value: str) -> bool:
    return bool(_ISIN_PATTERN.match(value.strip().upper()))


def _resolve_symbol_via_search(query: str) -> dict:
    try:
        search = yf.Search(query, max_results=1)
        quotes = getattr(search, "quotes", None) or []
        if quotes:
            return {"symbol": quotes[0].get("symbol"), "exchange": quotes[0].get("exchange")}
    except Exception:
        pass
    return {}


def get_snapshot(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
    except Exception as exc:
        raise ValueError(f"Daten für Ticker '{ticker}' nicht abrufbar: {exc}") from exc

    price = info.get("regularMarketPrice") or info.get("currentPrice")
    if not info or price is None:
        raise ValueError(f"Keine Daten für Ticker '{ticker}' gefunden – Symbol/Börsen-Suffix prüfen")

    symbol = info.get("symbol")
    exchange = info.get("exchange")

    if _is_isin(ticker) and (not symbol or symbol.upper() == ticker.strip().upper()):
        resolved = _resolve_symbol_via_search(ticker)
        symbol = resolved.get("symbol") or symbol
        exchange = resolved.get("exchange") or exchange

    ex_dividend_date = None
    ex_div_raw = info.get("exDividendDate")
    if ex_div_raw:
        try:
            ex_dividend_date = datetime.utcfromtimestamp(ex_div_raw).strftime("%Y-%m-%d")
        except (ValueError, OSError, OverflowError):
            ex_dividend_date = None

    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName"),
        "symbol": symbol,
        "exchange": exchange,
        "currency": info.get("currency"),
        "current_price": price,
        "previous_close": info.get("previousClose"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "dividend_yield": info.get("dividendYield"),
        "ex_dividend_date": ex_dividend_date,
        "beta": info.get("beta"),
        "business_summary": info.get("longBusinessSummary"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


def get_price_history_series(ticker: str, period: str = "6mo") -> list:
    interval = PERIOD_INTERVALS.get(period, "1d")
    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception:
        return []
    if hist.empty:
        return []
    closes = hist["Close"]
    date_format = "%Y-%m-%d %H:%M" if period in ("1d", "5d") else "%Y-%m-%d"
    result = []
    for idx, value in closes.items():
        if value is None or math.isnan(value):
            continue
        result.append({"date": idx.strftime(date_format), "close": round(float(value), 2)})
    return result
