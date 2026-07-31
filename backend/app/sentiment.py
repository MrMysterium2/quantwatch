import logging
from datetime import datetime, timezone
from typing import List, Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger("quantwatch")

MODEL_NAME = "ProsusAI/finbert"
LABELS = ["positive", "negative", "neutral"]

SOURCE_WEIGHTS = {
    "reuters": 1.5,
    "bloomberg": 1.5,
    "associated press": 1.4,
    "ap": 1.4,
    "dow jones": 1.4,
    "the wall street journal": 1.4,
    "wsj": 1.4,
    "cnbc": 1.2,
    "marketwatch": 1.1,
    "yahoo": 1.0,
    "business wire": 1.0,
    "pr newswire": 0.9,
    "seeking alpha": 0.8,
    "benzinga": 0.8,
    "motley fool": 0.7,
    "zacks": 0.7,
}
DEFAULT_SOURCE_WEIGHT = 0.9
RECENCY_HALF_LIFE_HOURS = 24.0

_tokenizer: Optional[AutoTokenizer] = None
_model: Optional[AutoModelForSequenceClassification] = None


def _load_model():
    global _tokenizer, _model
    if _model is None:
        logger.info("Lade FinBERT-Modell (%s) - beim ersten Aufruf, danach im Speicher gehalten", MODEL_NAME)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        _model.eval()
        logger.info("FinBERT-Modell geladen.")
    return _tokenizer, _model


def analyze_text(text: str) -> dict:
    tokenizer, model = _load_model()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0].tolist()

    result = dict(zip(LABELS, probs))
    result["score"] = result["positive"] - result["negative"]
    return result


def _source_weight(source: str) -> float:
    return SOURCE_WEIGHTS.get((source or "").strip().lower(), DEFAULT_SOURCE_WEIGHT)


def _recency_weight(published_unix: float) -> float:
    age_hours = (datetime.now(timezone.utc).timestamp() - published_unix) / 3600
    age_hours = max(age_hours, 0)
    return 0.5 ** (age_hours / RECENCY_HALF_LIFE_HOURS)


def aggregate_sentiment(articles: List[dict], max_articles: int = 20) -> dict:
    if not articles:
        return {"score": None, "article_count": 0, "top_articles": []}

    weighted_sum = 0.0
    weight_total = 0.0
    scored = []

    total = min(len(articles), max_articles)
    logger.info("Analysiere %d Artikel mit FinBERT ...", total)

    for i, article in enumerate(articles[:max_articles], start=1):
        text = f"{article.get('headline', '')}. {article.get('summary', '')}".strip()
        if not text or text == ".":
            continue

        sentiment = analyze_text(text)
        logger.info("  [%d/%d] %s -> score=%.3f", i, total, (article.get('source') or '?'), sentiment["score"])

        w_source = _source_weight(article.get("source", ""))
        w_recency = _recency_weight(article.get("datetime", 0))
        weight = w_source * w_recency

        weighted_sum += sentiment["score"] * weight
        weight_total += weight

        scored.append({
            "headline": article.get("headline"),
            "source": article.get("source"),
            "url": article.get("url"),
            "sentiment_score": round(sentiment["score"], 3),
            "weight": round(weight, 3),
        })

    if weight_total == 0:
        return {"score": None, "article_count": len(articles), "top_articles": []}

    return {
        "score": round(weighted_sum / weight_total, 3),
        "article_count": len(articles),
        "top_articles": sorted(scored, key=lambda a: a["weight"], reverse=True)[:5],
    }
