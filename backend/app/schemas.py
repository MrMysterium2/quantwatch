import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

COMMON_WEAK_PASSWORDS = {
    "passwortpasswort", "passwort123456", "willkommen123456", "adminadminadmin",
    "123456789012345", "qwertzuiopasdfg", "letmeinletmeinx", "iloveyouiloveyou",
    "aktientoolaktien", "unternehmenaktie",
}


def _has_sequential_digits(password: str, run_length: int = 4) -> bool:
    for group in re.findall(r"\d+", password):
        for i in range(len(group) - run_length + 1):
            window = [int(c) for c in group[i:i + run_length]]
            ascending = all(window[j + 1] - window[j] == 1 for j in range(len(window) - 1))
            descending = all(window[j] - window[j + 1] == 1 for j in range(len(window) - 1))
            if ascending or descending:
                return True
    return False


class WatchlistCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16, description="Boersenkuerzel, z. B. AAPL oder SAP.DE")
    notes: Optional[str] = Field(None, max_length=2000, description="Freitext, fliesst nicht ins Scoring ein")
    purchase_price: Optional[float] = Field(None, gt=0, description="Kaufpreis pro Stueck (optional)")
    quantity: Optional[float] = Field(None, gt=0, description="Anzahl gehaltener Stuecke (optional)")
    price_target: Optional[float] = Field(None, gt=0, description="Kursziel fuer Alert (optional)")

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Ticker darf nicht leer sein")
        return v


class BulkWatchlistCreate(BaseModel):
    tickers: List[str] = Field(..., min_length=1, max_length=200)


class WatchlistUpdate(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)
    purchase_price: Optional[float] = Field(None, gt=0)
    quantity: Optional[float] = Field(None, gt=0)
    price_target: Optional[float] = Field(None, gt=0)


class WatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: Optional[str]
    sector: Optional[str]
    symbol: Optional[str]
    exchange: Optional[str]
    notes: Optional[str]
    purchase_price: Optional[float]
    quantity: Optional[float]
    price_target: Optional[float]
    added_at: datetime


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    created_at: datetime
    recommendation: str
    expected_return_pct: float
    risk_score: float
    technical_score: Optional[float]
    fundamental_score: Optional[float]
    sentiment_score: Optional[float]
    reasoning: Optional[str]


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(
        ..., min_length=12, max_length=128,
        description="Mind. 12 Zeichen, inkl. Gross-/Kleinbuchstabe, Zahl und Sonderzeichen",
    )

    @field_validator("username")
    @classmethod
    def username_clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Benutzername darf nicht leer sein")
        return v

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str, info: ValidationInfo) -> str:
        if v.lower() in COMMON_WEAK_PASSWORDS:
            raise ValueError("Dieses Passwort ist zu häufig verwendet und unsicher")

        username = (info.data or {}).get("username", "")
        if username and username.lower() in v.lower():
            raise ValueError("Passwort darf den Benutzernamen nicht enthalten")

        if not re.search(r"[A-ZÄÖÜ]", v):
            raise ValueError("Passwort muss mindestens einen Großbuchstaben enthalten")
        if not re.search(r"[a-zäöüß]", v):
            raise ValueError("Passwort muss mindestens einen Kleinbuchstaben enthalten")
        if not re.search(r"\d", v):
            raise ValueError("Passwort muss mindestens eine Zahl enthalten")
        if not re.search(r"[^A-Za-z0-9ÄÖÜäöüß]", v):
            raise ValueError("Passwort muss mindestens ein Sonderzeichen enthalten")

        if _has_sequential_digits(v):
            raise ValueError(
                "Passwort darf keine auf- oder absteigende Zahlenfolge (z. B. 1234, 9876) enthalten"
            )

        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., description="Zur Bestätigung erneut das aktuelle Passwort eingeben")
