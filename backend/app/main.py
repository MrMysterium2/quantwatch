import csv
import io
import json
import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from alerts import evaluate_alerts, send_discord_alert
from auth import create_access_token, get_current_user, hash_password, verify_password
from backtest import run_backtest
from db import engine, get_db
from explain import explain_fundamental, explain_risk, explain_trend
from translate import translate_to_german
from finnhub_client import get_company_news, get_upcoming_earnings
from market_data import get_price_history_series, get_snapshot
from models import Empfehlung, User, Watchlist
from models import Score as ScoreModel
from schemas import (
    BulkWatchlistCreate,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    ScoreRead,
    WatchlistCreate,
    WatchlistRead,
    WatchlistUpdate,
)
from scoring import generate_recommendation
from sentiment import aggregate_sentiment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quantwatch")

app = FastAPI(title="QuantWatch", version="0.1.0")
app.add_middleware(GZipMiddleware, minimum_size=500)


def _safe(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _get_latest_score(db: Session, ticker: str) -> Optional[ScoreModel]:
    return (
        db.query(ScoreModel)
        .filter(ScoreModel.ticker == ticker)
        .order_by(ScoreModel.created_at.desc())
        .first()
    )


def _get_latest_scores_bulk(db: Session, tickers: List[str]) -> Dict[str, ScoreModel]:
    if not tickers:
        return {}

    latest_subq = (
        db.query(ScoreModel.ticker, func.max(ScoreModel.created_at).label("max_created"))
        .filter(ScoreModel.ticker.in_(tickers))
        .group_by(ScoreModel.ticker)
        .subquery()
    )

    rows = (
        db.query(ScoreModel)
        .join(
            latest_subq,
            (ScoreModel.ticker == latest_subq.c.ticker)
            & (ScoreModel.created_at == latest_subq.c.max_created),
        )
        .all()
    )

    return {row.ticker: row for row in rows}


def _compute_gain_loss(entry: Watchlist, current_price: Optional[float]) -> Optional[dict]:
    if not entry.purchase_price or not entry.quantity or current_price is None:
        return None

    invested = entry.purchase_price * entry.quantity
    current_value = current_price * entry.quantity
    gain_loss_abs = round(current_value - invested, 2)
    gain_loss_pct = round((current_price - entry.purchase_price) / entry.purchase_price * 100, 2)

    return {
        "invested": round(invested, 2),
        "current_value": round(current_value, 2),
        "gain_loss_abs": gain_loss_abs,
        "gain_loss_pct": gain_loss_pct,
    }


_login_attempts: dict = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15


def _check_login_rate_limit(username: str) -> None:
    now = datetime.now()
    window_start = now - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    attempts = [t for t in _login_attempts[username] if t > window_start]
    _login_attempts[username] = attempts
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=f"Zu viele fehlgeschlagene Loginversuche - bitte in {LOGIN_WINDOW_MINUTES} Minuten erneut versuchen",
        )


def _record_failed_login(username: str) -> None:
    _login_attempts[username].append(datetime.now())


def _persist_score(db: Session, result: dict) -> ScoreModel:
    technical = result["details"]["technical"]
    fundamental = result["details"]["fundamental"]
    risk = result["details"]["risk"]
    earnings = result["details"].get("upcoming_earnings")
    days_to_earnings = result["details"].get("days_to_earnings")

    entry = ScoreModel(
        ticker=result["ticker"],
        recommendation=Empfehlung(result["recommendation"]),
        expected_return_pct=result["expected_return_pct"],
        risk_score=result["risk_score"],
        technical_score=result["technical_score"],
        fundamental_score=result["fundamental_score"],
        sentiment_score=result["sentiment_score"],
        reasoning=result["reasoning"],
        current_price=technical.get("current_price"),
        sma50=technical.get("sma50"),
        sma200=technical.get("sma200"),
        rsi=technical.get("rsi"),
        trailing_pe=fundamental.get("trailing_pe"),
        forward_pe=fundamental.get("forward_pe"),
        volatility_pct=risk.get("annualized_volatility_pct"),
        beta=risk.get("beta"),
        next_earnings_date=(earnings or {}).get("date"),
        days_to_earnings=days_to_earnings,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except OperationalError as exc:
        logger.error("DB-Verbindung fehlgeschlagen: %s", exc)
        raise HTTPException(status_code=503, detail=f"DB nicht erreichbar: {exc}") from exc


@app.post("/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Benutzername bereits vergeben")

    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.username)
    return {"access_token": token, "token_type": "bearer", "username": user.username}


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    _check_login_rate_limit(payload.username)

    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        _record_failed_login(payload.username)
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort falsch")

    token = create_access_token(user.id, user.username)
    return {"access_token": token, "token_type": "bearer", "username": user.username}


@app.post("/auth/delete-account", status_code=204)
def delete_account(
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Passwort falsch - Löschung abgebrochen")

    db.delete(current_user)
    db.commit()
    return None


@app.post("/watchlist", response_model=WatchlistRead, status_code=201)
def add_to_watchlist(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_name = None
    sector = None
    symbol = None
    exchange = None
    try:
        snapshot = get_snapshot(payload.ticker)
        company_name = snapshot.get("name")
        sector = snapshot.get("sector")
        symbol = snapshot.get("symbol")
        exchange = snapshot.get("exchange")
    except ValueError:
        pass

    entry = Watchlist(
        user_id=current_user.id,
        ticker=payload.ticker,
        name=company_name,
        sector=sector,
        symbol=symbol,
        exchange=exchange,
        notes=payload.notes,
        purchase_price=payload.purchase_price,
        quantity=payload.quantity,
        price_target=payload.price_target,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ticker '{payload.ticker}' ist bereits auf deiner Watchlist"
        )
    db.refresh(entry)
    return entry


@app.post("/watchlist/bulk")
def add_multiple_to_watchlist(
    payload: BulkWatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = []
    for raw_ticker in payload.tickers:
        ticker = raw_ticker.strip().upper()
        if not ticker:
            continue

        company_name = None
        sector = None
        symbol = None
        exchange = None
        try:
            snapshot = get_snapshot(ticker)
            company_name = snapshot.get("name")
            sector = snapshot.get("sector")
            symbol = snapshot.get("symbol")
            exchange = snapshot.get("exchange")
        except ValueError as exc:
            logger.warning("Watchlist-Bulk-Add fuer '%s' fehlgeschlagen: %s", ticker, exc)
            results.append({"ticker": ticker, "status": "fehler", "detail": "Ticker nicht gefunden oder ungueltig"})
            continue

        entry = Watchlist(
            user_id=current_user.id, ticker=ticker, name=company_name,
            sector=sector, symbol=symbol, exchange=exchange,
        )
        db.add(entry)
        try:
            db.commit()
            results.append({"ticker": ticker, "status": "hinzugefuegt"})
        except IntegrityError:
            db.rollback()
            results.append({"ticker": ticker, "status": "bereits_vorhanden"})

    return {"results": results}


@app.patch("/watchlist/{ticker}", response_model=WatchlistRead)
def update_watchlist_entry(
    ticker: str,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id, Watchlist.ticker == ticker.strip().upper())
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' nicht auf deiner Watchlist gefunden")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return entry


@app.get("/watchlist", response_model=List[WatchlistRead])
def list_watchlist(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )


@app.get("/watchlist/overview")
def watchlist_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entries = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )
    overview = []
    latest_scores = _get_latest_scores_bulk(db, [entry.ticker for entry in entries])
    for entry in entries:
        latest = latest_scores.get(entry.ticker)
        current_price = _safe(latest.current_price) if latest else None
        overview.append({
            "id": entry.id,
            "ticker": entry.ticker,
            "name": entry.name,
            "sector": entry.sector,
            "symbol": entry.symbol,
            "exchange": entry.exchange,
            "notes": entry.notes,
            "purchase_price": entry.purchase_price,
            "quantity": entry.quantity,
            "price_target": entry.price_target,
            "gain_loss": _compute_gain_loss(entry, current_price),
            "added_at": entry.added_at.isoformat(),
            "latest_score": {
                "recommendation": latest.recommendation.value,
                "expected_return_pct": _safe(latest.expected_return_pct),
                "risk_score": _safe(latest.risk_score),
                "technical_score": _safe(latest.technical_score),
                "fundamental_score": _safe(latest.fundamental_score),
                "current_price": current_price,
                "sma50": _safe(latest.sma50),
                "sma200": _safe(latest.sma200),
                "rsi": _safe(latest.rsi),
                "trailing_pe": _safe(latest.trailing_pe),
                "reasoning": latest.reasoning,
                "created_at": latest.created_at.isoformat(),
            } if latest else None,
        })
    return overview


@app.get("/watchlist/export")
def export_watchlist(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entries = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.ticker)
        .all()
    )
    latest_scores = _get_latest_scores_bulk(db, [entry.ticker for entry in entries])

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Ticker", "Name", "Sektor", "Notizen", "Kaufpreis", "Stueckzahl", "Kursziel",
        "Aktueller Kurs", "Empfehlung", "Erwartete Rendite %", "Risiko-Score",
        "Investiert", "Aktueller Wert", "Gewinn/Verlust", "Gewinn/Verlust %",
    ])

    for entry in entries:
        latest = latest_scores.get(entry.ticker)
        current_price = latest.current_price if latest else None
        gain_loss = _compute_gain_loss(entry, current_price)

        writer.writerow([
            entry.ticker,
            entry.name or "",
            entry.sector or "",
            entry.notes or "",
            entry.purchase_price or "",
            entry.quantity or "",
            entry.price_target or "",
            current_price or "",
            latest.recommendation.value if latest else "",
            latest.expected_return_pct if latest else "",
            latest.risk_score if latest else "",
            gain_loss["invested"] if gain_loss else "",
            gain_loss["current_value"] if gain_loss else "",
            gain_loss["gain_loss_abs"] if gain_loss else "",
            gain_loss["gain_loss_pct"] if gain_loss else "",
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=watchlist.csv"},
    )


@app.delete("/watchlist/{ticker}", status_code=204)
def remove_from_watchlist(
    ticker: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id, Watchlist.ticker == ticker.strip().upper())
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' nicht auf deiner Watchlist gefunden")
    db.delete(entry)
    db.commit()
    return None


@app.get("/stocks/{ticker}/snapshot")
def stock_snapshot(ticker: str):
    try:
        return get_snapshot(ticker.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/stocks/{ticker}/insights")
def stock_insights(ticker: str):
    ticker = ticker.strip().upper()

    finnhub_symbol = ticker
    try:
        snapshot = get_snapshot(ticker)
        finnhub_symbol = snapshot.get("symbol") or ticker
    except ValueError:
        pass

    articles = get_company_news(finnhub_symbol)
    sentiment = aggregate_sentiment(articles) if articles else None
    earnings = get_upcoming_earnings(finnhub_symbol)

    if sentiment is None and earnings is None:
        return {
            "ticker": ticker,
            "available": False,
            "reason": "Keine Finnhub-Daten verfuegbar (internationaler Ticker oder FINNHUB_API_KEY fehlt)",
        }

    return {
        "ticker": ticker,
        "available": True,
        "news_sentiment": sentiment,
        "upcoming_earnings": earnings,
    }


@app.post("/stocks/{ticker}/score")
def score_stock(ticker: str, db: Session = Depends(get_db)):
    ticker_upper = ticker.strip().upper()
    previous = _get_latest_score(db, ticker_upper)
    previous_recommendation = previous.recommendation.value if previous else None

    try:
        result = generate_recommendation(ticker, previous_recommendation=previous_recommendation)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _persist_score(db, result)
    return result


@app.get("/stocks/{ticker}/scores", response_model=List[ScoreRead])
def score_history(ticker: str, limit: int = 50, db: Session = Depends(get_db)):
    ticker = ticker.strip().upper()
    return (
        db.query(ScoreModel)
        .filter(ScoreModel.ticker == ticker)
        .order_by(ScoreModel.created_at.desc())
        .limit(limit)
        .all()
    )


ALLOWED_CHART_PERIODS = {"1d", "5d", "1mo", "6mo", "ytd", "1y", "5y"}


def _truncate(text, max_len: int = 500):
    if not text:
        return None
    text = text.strip()
    if len(text) <= max_len:
        return text

    excerpt = text[:max_len]
    last_period = excerpt.rfind(". ")
    if last_period > 100:
        return excerpt[: last_period + 1]
    return excerpt.rsplit(" ", 1)[0] + "…"


@app.get("/stocks/{ticker}/details")
def stock_details(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.strip().upper()

    latest = _get_latest_score(db, ticker)

    if latest is None:
        try:
            result = generate_recommendation(ticker)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        latest = _persist_score(db, result)

    try:
        snapshot = get_snapshot(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    price_history = get_price_history_series(ticker, period="6mo")

    technical = {
        "current_price": _safe(latest.current_price),
        "sma50": _safe(latest.sma50),
        "sma200": _safe(latest.sma200),
        "rsi": _safe(latest.rsi),
    }
    fundamental = {
        "score": _safe(latest.fundamental_score),
        "trailing_pe": _safe(latest.trailing_pe),
        "forward_pe": _safe(latest.forward_pe),
    }
    risk = {
        "score": _safe(latest.risk_score),
        "annualized_volatility_pct": _safe(latest.volatility_pct),
        "beta": _safe(latest.beta),
    }

    next_earnings = None
    if latest.next_earnings_date:
        next_earnings = {"date": latest.next_earnings_date, "days": latest.days_to_earnings}

    yahoo_symbol = snapshot.get("symbol") or ticker

    return {
        "ticker": ticker,
        "name": snapshot.get("name"),
        "sector": snapshot.get("sector"),
        "symbol": snapshot.get("symbol"),
        "exchange": snapshot.get("exchange"),
        "recommendation": latest.recommendation.value,
        "expected_return_pct": _safe(latest.expected_return_pct),
        "risk_score": _safe(latest.risk_score),
        "as_of": latest.created_at.isoformat(),
        "business_summary": _truncate(translate_to_german(snapshot.get("business_summary"))),
        "next_earnings": next_earnings,
        "dividend_yield": _safe(snapshot.get("dividend_yield")),
        "ex_dividend_date": snapshot.get("ex_dividend_date"),
        "price_history": price_history,
        "technical": technical,
        "fundamental": fundamental,
        "risk": risk,
        "trend_explanation": explain_trend(technical),
        "kgv_explanation": explain_fundamental(fundamental),
        "risk_explanation": explain_risk(risk, latest.days_to_earnings),
        "yahoo_finance_url": f"https://finance.yahoo.com/quote/{yahoo_symbol}",
        "yahoo_news_url": f"https://finance.yahoo.com/quote/{yahoo_symbol}/news",
    }


@app.get("/stocks/{ticker}/chart")
def stock_chart(ticker: str, period: str = "6mo"):
    ticker = ticker.strip().upper()
    if period not in ALLOWED_CHART_PERIODS:
        raise HTTPException(status_code=400, detail=f"Ungültiger Zeitraum. Erlaubt: {sorted(ALLOWED_CHART_PERIODS)}")
    history = get_price_history_series(ticker, period=period)
    return {"ticker": ticker, "period": period, "price_history": history}


@app.post("/watchlist/scan")
def scan_watchlist(db: Session = Depends(get_db)):
    watchlist_entries = db.query(Watchlist).all()
    results = []
    FINNHUB_RATE_LIMIT_DELAY_SECONDS = 2.5

    previous_scores = _get_latest_scores_bulk(db, [entry.ticker for entry in watchlist_entries])

    for i, entry in enumerate(watchlist_entries):
        if i > 0:
            time.sleep(FINNHUB_RATE_LIMIT_DELAY_SECONDS)

        previous_score = previous_scores.get(entry.ticker)
        previous_recommendation = previous_score.recommendation.value if previous_score else None

        try:
            result = generate_recommendation(entry.ticker, previous_recommendation=previous_recommendation)
        except Exception as exc:
            logger.warning("Scoring fuer %s fehlgeschlagen: %s", entry.ticker, exc)
            results.append({"ticker": entry.ticker, "error": "Scoring fehlgeschlagen"})
            continue

        if entry.sector is None and result.get("sector"):
            entry.sector = result.get("sector")
        if entry.symbol is None and result.get("symbol"):
            entry.symbol = result.get("symbol")
        if entry.exchange is None and result.get("exchange"):
            entry.exchange = result.get("exchange")

        days_to_earnings = result["details"].get("days_to_earnings")
        alerts = evaluate_alerts(previous_score, result, days_to_earnings, watchlist_entry=entry)
        for message in alerts:
            send_discord_alert(message)

        _persist_score(db, result)
        results.append({
            "ticker": result["ticker"],
            "recommendation": result["recommendation"],
            "expected_return_pct": result["expected_return_pct"],
            "risk_score": result["risk_score"],
            "alerts_sent": alerts,
        })

    return {"scanned": len(watchlist_entries), "results": results}


@app.get("/backtest")
def backtest(db: Session = Depends(get_db)):
    all_scores = db.query(ScoreModel).all()
    result = run_backtest(all_scores)
    result["pending_count"] = len(all_scores) - result["evaluated_count"]
    return result


app.mount("/", StaticFiles(directory="static", html=True), name="dashboard")
