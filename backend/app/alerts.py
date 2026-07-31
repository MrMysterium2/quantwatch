import logging
import os
from datetime import datetime
from typing import List, Optional

import requests

logger = logging.getLogger("quantwatch")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

RISK_THRESHOLD = 70.0
EARNINGS_WARNING_DAYS = 7
EARNINGS_ALERT_HOUR = 8
DIVIDEND_WARNING_DAYS = 7


def send_discord_alert(message: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL nicht gesetzt - Alert wird nur geloggt: %s", message)
        return
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Discord-Alert konnte nicht gesendet werden: %s", exc)


def evaluate_alerts(
    previous_score,
    result: dict,
    days_to_earnings: Optional[int],
    watchlist_entry=None,
    now: Optional[datetime] = None,
) -> List[str]:
    if now is None:
        now = datetime.now()

    messages: List[str] = []
    ticker = result["ticker"]
    display_name = result.get("name") or ticker
    recommendation = result["recommendation"]
    risk_score = result["risk_score"]
    current_price = result["details"]["technical"].get("current_price")

    previous_recommendation = previous_score.recommendation.value if previous_score else None
    if recommendation in ("kaufen", "verkaufen") and recommendation != previous_recommendation:
        richtung = "📈 KAUFEN" if recommendation == "kaufen" else "📉 VERKAUFEN"
        vorher = previous_recommendation or "keine Historie"
        messages.append(
            f"**{display_name}** ({ticker}): Neue Empfehlung {richtung} (vorher: {vorher}) "
            f"- erwartete Rendite {result['expected_return_pct']}%, Risiko {risk_score}"
        )

    previous_risk = previous_score.risk_score if previous_score else 0.0
    if risk_score > RISK_THRESHOLD and previous_risk <= RISK_THRESHOLD:
        messages.append(
            f"**{display_name}** ({ticker}): ⚠️ Risiko-Score stark gestiegen auf {risk_score} (Schwelle: {RISK_THRESHOLD})"
        )

    if (
        days_to_earnings is not None
        and days_to_earnings <= EARNINGS_WARNING_DAYS
        and now.hour == EARNINGS_ALERT_HOUR
    ):
        messages.append(
            f"**{display_name}** ({ticker}): 📅 Earnings in {days_to_earnings} Tagen - erhöhte Kursschwankung möglich"
        )

    if watchlist_entry is not None and watchlist_entry.price_target and current_price is not None:
        target = watchlist_entry.price_target
        previous_price = previous_score.current_price if previous_score else None
        reached_now = current_price >= target
        reached_before = previous_price is not None and previous_price >= target
        if reached_now and not reached_before:
            messages.append(
                f"**{display_name}** ({ticker}): 🎯 Kursziel {target} erreicht! Aktueller Kurs: {current_price}"
            )

    return messages
