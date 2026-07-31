# QuantWatch

*[🇩🇪 Deutsche Version → README.de.md](README.de.md)*

> ⚠️ **Not an investment or recommendation tool.** This project is a private
> homelab/learning project exploring APIs, scoring logic, and Docker
> infrastructure. It is a **rule-based composite scoring model built on
> publicly available market data** — **not** a validated forecasting AI, not
> financial advice, and not a buy/sell recommendation under applicable
> financial regulation (e.g. the German KWG). The weights in the scoring
> model are manually chosen and not empirically validated. Use at your own
> risk; investment decisions should never be based solely on this tool.

## What does it do?

Multi-user watchlist management with automated stock scoring based on:

- **Technical**: SMA50/SMA200 trend, RSI (via [yfinance](https://github.com/ranaroussi/yfinance))
- **Fundamental**: P/E trend (trailing vs. forward P/E)
- **Sentiment**: News sentiment via [FinBERT](https://huggingface.co/ProsusAI/finbert), weighted by source and recency
- **Risk**: annualized volatility, beta, proximity to earnings dates

Output: recommendation (Buy/Hold/Sell) + expected return % + risk score,
including a plain-text explanation. Also includes: Discord alerting on
recommendation changes, hourly watchlist scan (systemd timer), backtest
evaluation, CSV export, portfolio tracking.

## Architecture

```
docker-compose.yml       # Postgres 16 + FastAPI backend, both bound to 127.0.0.1 only
backend/
  Dockerfile
  requirements.txt
  app/
    main.py               # FastAPI routes
    auth.py                # JWT auth (HS256), bcrypt password hashing
    db.py                   # SQLAlchemy engine/session
    models.py                # ORM models (User, Watchlist, Score)
    schemas.py                 # Pydantic schemas incl. password policy
    market_data.py              # yfinance integration, ISIN resolution
    finnhub_client.py             # Finnhub client (earnings, news)
    sentiment.py                    # FinBERT sentiment analysis
    scoring.py                       # Scoring engine
    alerts.py                         # Discord webhook alerting
    backtest.py                        # Recommendation vs. actual price movement
    explain.py                          # Plain-text explanations
    translate.py                         # Translation via deep-translator
    alembic/                              # DB migrations
```

Core components are deliberately split into independent modules so individual
data sources can be swapped out without touching the scoring logic itself.

## APIs Used

| API | Purpose | Cost |
|---|---|---|
| [yfinance](https://github.com/ranaroussi/yfinance) | Price/fundamental data (unofficial, no API key) | free |
| [Finnhub](https://finnhub.io) | Earnings calendar, company news | free tier (US tickers only) |
| [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) | News sentiment (local via Transformers, no API call) | free, ~2 GB model cache |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | Business summary translation | unofficial Google Translate interface, no SLA |
| Discord Webhook | Alerting | free |

## Setup

**Requirements:** Docker + Docker Compose, a free port (default 8000 inside
the container, map to whichever host port you want in
`docker-compose.yml`), ~2 GB of storage for the FinBERT model cache
(CPU-only).

```bash
git clone <this-repo>
cd quantwatch

cp .env.example .env
nano .env   # set POSTGRES_PASSWORD, FINNHUB_API_KEY, DISCORD_WEBHOOK_URL, JWT_SECRET
            # generate JWT_SECRET with: openssl rand -hex 32

docker compose up -d --build
```

Health check:
```bash
curl http://127.0.0.1:8095/health
```

**Note:** `FINNHUB_API_KEY` and `DISCORD_WEBHOOK_URL` are optional — without
them the backend still runs, it just won't return earnings/news data or send
Discord alerts (they're only logged instead).

## Security Notes for Your Own Deployment

- Ports are bound to `127.0.0.1` by default — for internet exposure, put a
  reverse proxy with TLS (nginx, Caddy) in front and plan additional
  hardening (rate limiting, WAF).
- `JWT_SECRET` is required — the backend refuses to start without it set.
- Password policy enforces minimum length, character classes, and rejects
  common weak passwords server-side (see `schemas.py`).
- Login rate limiting (5 attempts / 15 minutes per username) is built in.

## License

MIT — see `LICENSE`.

## Additional Disclaimer

This software produces a rule-based score derived from publicly available
market data (yfinance, Finnhub) and an open-source sentiment model
(ProsusAI/finbert). It does not constitute financial, investment, or legal
advice under applicable financial regulation (e.g. the German KWG). No
warranty is made regarding the accuracy, completeness, or suitability of any
output for investment decisions. Use at your own risk.
