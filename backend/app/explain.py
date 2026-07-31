from typing import Optional


def explain_trend(technical: dict) -> str:
    price = technical.get("current_price")
    sma50 = technical.get("sma50")
    sma200 = technical.get("sma200")
    rsi = technical.get("rsi")

    parts = []
    if sma50 is not None and sma200 is not None and price is not None:
        if price > sma50 > sma200:
            parts.append(
                f"Der Kurs ({price}) liegt über dem SMA50 ({sma50}), der wiederum über dem "
                f"SMA200 ({sma200}) liegt - ein klassisches Aufwärtstrend-Muster (\"Golden Cross\"-Lage)."
            )
        elif price < sma50 < sma200:
            parts.append(
                f"Der Kurs ({price}) liegt unter dem SMA50 ({sma50}), der wiederum unter dem "
                f"SMA200 ({sma200}) liegt - das deutet auf einen Abwärtstrend hin (\"Death Cross\"-Lage)."
            )
        elif price > sma50:
            parts.append(
                f"Der Kurs ({price}) liegt über dem SMA50 ({sma50}), das Gesamtbild ist aber "
                f"gemischt (SMA200: {sma200}) - kein eindeutiger Trend."
            )
        else:
            parts.append(
                f"Der Kurs ({price}) liegt unter dem SMA50 ({sma50}), das Gesamtbild ist aber "
                f"gemischt (SMA200: {sma200})."
            )
    elif sma50 is not None and price is not None:
        richtung = "über" if price > sma50 else "unter"
        parts.append(
            f"Der Kurs ({price}) liegt {richtung} dem SMA50 ({sma50}). Für den SMA200 liegt "
            f"noch nicht genug Kurshistorie vor (z.B. bei neueren Börsengängen)."
        )
    else:
        parts.append("Für eine Trendaussage liegt nicht genug Kurshistorie vor.")

    if rsi is not None:
        if rsi > 70:
            parts.append(f"Der RSI von {rsi} deutet auf eine überkaufte Lage hin - kurzfristig steigt das Risiko eines Rücksetzers.")
        elif rsi < 30:
            parts.append(f"Der RSI von {rsi} deutet auf eine überverkaufte Lage hin - eine Erholung wird wahrscheinlicher.")
        else:
            parts.append(f"Der RSI liegt mit {rsi} im neutralen Bereich (weder über- noch unterkauft).")

    return " ".join(parts)


def explain_fundamental(fundamental: dict) -> str:
    trailing_pe = fundamental.get("trailing_pe")
    forward_pe = fundamental.get("forward_pe")

    if trailing_pe is None or forward_pe is None:
        return "Für eine KGV-Einschätzung liegen nicht genug Daten vor (KGV oder Forward-KGV fehlt bei yfinance)."

    if forward_pe < trailing_pe:
        return (
            f"Das aktuelle KGV liegt bei {trailing_pe} (du zahlst also das {trailing_pe}-fache "
            f"des Jahresgewinns). Das Forward-KGV liegt mit {forward_pe} niedriger - der Markt "
            f"erwartet also Gewinnwachstum, was das Wachstumssignal positiv macht."
        )
    elif forward_pe > trailing_pe:
        return (
            f"Das aktuelle KGV liegt bei {trailing_pe}. Das Forward-KGV liegt mit {forward_pe} "
            f"höher als das aktuelle - der Markt erwartet also einen Gewinnrückgang, was das "
            f"Wachstumssignal negativ macht."
        )
    else:
        return f"KGV ({trailing_pe}) und Forward-KGV ({forward_pe}) liegen etwa gleichauf - kein klares Wachstums- oder Rückgangssignal."


def explain_risk(risk: dict, days_to_earnings: Optional[int]) -> str:
    vol = risk.get("annualized_volatility_pct")
    beta = risk.get("beta")

    parts = []
    if vol is not None:
        parts.append(
            f"Die annualisierte Volatilität liegt bei {vol}% - das beschreibt, wie stark der "
            f"Kurs im Jahresverlauf typischerweise schwankt (höher = größere Kursausschläge in beide Richtungen)."
        )
    if beta is not None:
        if beta > 1.2:
            parts.append(f"Das Beta von {beta} zeigt, dass die Aktie deutlich stärker schwankt als der Gesamtmarkt.")
        elif beta < 0.8:
            parts.append(f"Das Beta von {beta} zeigt, dass die Aktie defensiver ist als der Gesamtmarkt.")
        else:
            parts.append(f"Das Beta von {beta} liegt nah am Marktdurchschnitt.")
    if days_to_earnings is not None and days_to_earnings <= 7:
        parts.append(f"Zusätzlich stehen in {days_to_earnings} Tagen Quartalszahlen an, was kurzfristig für höhere Schwankungen sorgen kann.")

    if not parts:
        parts.append("Für eine detaillierte Risikoeinschätzung liegen nicht genug Daten vor.")

    return " ".join(parts)
