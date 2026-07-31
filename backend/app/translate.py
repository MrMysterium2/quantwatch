import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger("quantwatch")


def translate_to_german(text: str) -> str:
    if not text:
        return text
    try:
        return GoogleTranslator(source="en", target="de").translate(text)
    except Exception as exc:
        logger.warning("Übersetzung fehlgeschlagen, zeige Original-Text: %s", exc)
        return text
