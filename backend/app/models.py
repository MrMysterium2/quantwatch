import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Empfehlung(str, enum.Enum):
    KAUFEN = "kaufen"
    HALTEN = "halten"
    VERKAUFEN = "verkaufen"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    purchase_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    recommendation: Mapped[Empfehlung] = mapped_column(
        Enum(Empfehlung, name="empfehlung", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    expected_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)

    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fundamental_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trailing_pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    forward_pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volatility_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    beta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    next_earnings_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    days_to_earnings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    news_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
