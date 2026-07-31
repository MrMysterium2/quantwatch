# QuantWatch

*[🇬🇧 English version → README.md](README.md)*

> ⚠️ **Kein Anlage- oder Empfehlungstool.** Dieses Projekt ist ein privates
> Homelab-/Lernprojekt zur Auseinandersetzung mit APIs, Scoring-Logik und
> Docker-Infrastruktur. Es handelt sich um ein **regelbasiertes
> Composite-Scoring-Modell auf Basis frei zugänglicher Marktdaten** – **keine**
> validierte Prognose-KI, keine Finanzberatung und keine Kauf-/Verkaufsempfehlung
> im Sinne des deutschen Kreditwesengesetzes (KWG) oder vergleichbarer
> Regulierung. Die Gewichte im Scoring sind von Hand festgelegt und nicht
> empirisch validiert. Jede Nutzung erfolgt auf eigenes Risiko;
> Investitionsentscheidungen sollten nie allein auf Basis dieses Tools
> getroffen werden.

## Was macht das Tool?

Watchlist-Verwaltung (mehrbenutzerfähig) mit automatisierter Bewertung von
Aktien anhand von:

- **Technisch**: SMA50/SMA200-Trend, RSI (via [yfinance](https://github.com/ranaroussi/yfinance))
- **Fundamental**: KGV-Trend (Trailing- vs. Forward-KGV)
- **Sentiment**: News-Sentiment via [FinBERT](https://huggingface.co/ProsusAI/finbert), gewichtet nach Quelle und Aktualität
- **Risiko**: annualisierte Volatilität, Beta, Nähe zu Earnings-Terminen

Ergebnis: Empfehlung (Kaufen/Halten/Verkaufen) + erwartete Rendite % +
Risiko-Score, inkl. Klartext-Begründung. Zusätzlich: Discord-Alerting bei
Empfehlungswechsel, stündlicher Watchlist-Scan (systemd-Timer),
Backtest-Auswertung, CSV-Export, Portfolio-Tracking.

## Architektur

```
docker-compose.yml       # Postgres 16 + FastAPI-Backend, beide nur an 127.0.0.1 gebunden
backend/
  Dockerfile
  requirements.txt
  app/
    main.py               # FastAPI-Routen
    auth.py                # JWT-Auth (HS256), bcrypt-Passwort-Hashing
    db.py                   # SQLAlchemy Engine/Session
    models.py                # ORM-Modelle (User, Watchlist, Score)
    schemas.py                 # Pydantic-Schemas inkl. Passwort-Policy
    market_data.py              # yfinance-Anbindung, ISIN-Aufloesung
    finnhub_client.py             # Finnhub-Client (Earnings, News)
    sentiment.py                    # FinBERT-Sentimentanalyse
    scoring.py                       # Scoring-Engine
    alerts.py                         # Discord-Webhook-Alerting
    backtest.py                        # Empfehlung vs. tatsaechliche Kursentwicklung
    explain.py                          # Klartext-Erklaerungen
    translate.py                         # Uebersetzung via deep-translator
    alembic/                              # DB-Migrationen
```

Die Kernkomponenten sind bewusst als eigenständige Module getrennt, damit
einzelne Datenquellen ausgetauscht werden können, ohne die Scoring-Logik
anzufassen.

## Verwendete APIs

| API | Zweck | Kosten |
|---|---|---|
| [yfinance](https://github.com/ranaroussi/yfinance) | Kurs-/Fundamentaldaten (inoffiziell, kein API-Key) | kostenlos |
| [Finnhub](https://finnhub.io) | Earnings-Kalender, Company-News | kostenloser Free-Tier (nur US-Ticker) |
| [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) | News-Sentiment (lokal via Transformers, kein API-Call) | kostenlos, ~2 GB Modell-Cache |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | Übersetzung Firmenbeschreibung | inoffizielle Google-Translate-Schnittstelle, kein SLA |
| Discord Webhook | Alerting | kostenlos |

## Setup

**Voraussetzungen:** Docker + Docker Compose, freier Port (Standard 8000 im
Container, in `docker-compose.yml` auf gewünschten Host-Port mappen),
~2 GB Speicher für den FinBERT-Modell-Cache (CPU-only).

```bash
git clone <dieses-repo>
cd quantwatch

cp .env.example .env
nano .env   # POSTGRES_PASSWORD, FINNHUB_API_KEY, DISCORD_WEBHOOK_URL, JWT_SECRET eintragen
            # JWT_SECRET generieren mit: openssl rand -hex 32

docker compose up -d --build
```

Healthcheck:
```bash
curl http://127.0.0.1:8095/health
```

**Hinweis:** `FINNHUB_API_KEY` und `DISCORD_WEBHOOK_URL` sind optional – ohne
sie läuft das Backend, liefert aber keine Earnings-/News-Daten bzw. verschickt
keine Discord-Alerts (wird nur geloggt).

## Sicherheitshinweise für eigene Deployments

- Ports standardmäßig nur an `127.0.0.1` gebunden – für Internet-Exposition
  einen Reverse-Proxy mit TLS (nginx, Caddy) vorschalten und zusätzliche
  Absicherung (Rate-Limiting, WAF) einplanen.
- `JWT_SECRET` ist Pflicht – das Backend verweigert den Start ohne gesetzten
  Wert.
- Passwort-Policy erzwingt Mindestlänge, Zeichenklassen und sperrt gängige
  Schwachpasswörter serverseitig (siehe `schemas.py`).
- Login-Rate-Limiting (5 Versuche / 15 Minuten pro Benutzername) ist
  eingebaut.

## Lizenz

MIT – siehe `LICENSE`.

## Zusätzlicher Haftungsausschluss

Diese Software erzeugt ein regelbasiertes Scoring auf Basis frei zugänglicher
Marktdaten (yfinance, Finnhub) und eines Open-Source-Sentiment-Modells
(ProsusAI/finbert). Sie stellt keine Finanz-, Anlage- oder Rechtsberatung im
Sinne einschlägiger Finanzregulierung (z. B. des deutschen KWG) dar. Es wird
keine Gewähr für Richtigkeit, Vollständigkeit oder Eignung der Ausgaben für
Investitionsentscheidungen übernommen. Nutzung auf eigenes Risiko.
