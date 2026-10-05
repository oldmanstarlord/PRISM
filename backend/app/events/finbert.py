"""FinBERT sequence classification and deterministic fallback sentiment engine (D1, D3)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

FINBERT_MODEL_ID = "ProsusAI/finbert"
FINBERT_REVISION = "90eb618b0f7ca7067d2feae4d588523ee734c5db"
MAX_TOKENS = 512


@dataclass(frozen=True)
class SentimentScoreResult:
    model_name: str
    model_version: str
    sentiment: str  # "positive" | "negative" | "neutral"
    p_pos: float
    p_neg: float
    p_neu: float
    evidence_span: str | None


@dataclass(frozen=True)
class SentimentPrediction:
    sentiment: str  # "positive" | "negative" | "neutral"
    p_pos: float
    p_neg: float
    p_neu: float
    evidence_span: str


def chunk_text(text: str, max_tokens: int = MAX_TOKENS, overlap_tokens: int = 64) -> list[str]:
    """Chunk text into token-bounded segments with overlap for batch inference."""
    cleaned = text.strip()
    if not cleaned:
        return []

    words = cleaned.split()
    if len(words) <= max_tokens:
        return [cleaned]

    chunks: list[str] = []
    step = max(1, max_tokens - overlap_tokens)
    for i in range(0, len(words), step):
        chunk_words = words[i : i + max_tokens]
        chunks.append(" ".join(chunk_words))
        if i + max_tokens >= len(words):
            break
    return chunks


def aggregate_chunk_predictions(
    predictions: list[SentimentPrediction], method: str = "weighted_average"
) -> SentimentPrediction:
    """Aggregate multi-chunk predictions via weighted average or max sentiment."""
    if not predictions:
        return SentimentPrediction(
            sentiment="neutral",
            p_pos=0.0,
            p_neg=0.0,
            p_neu=1.0,
            evidence_span="",
        )

    if len(predictions) == 1:
        return predictions[0]

    n = len(predictions)
    avg_pos = sum(p.p_pos for p in predictions) / n
    avg_neg = sum(p.p_neg for p in predictions) / n
    avg_neu = sum(p.p_neu for p in predictions) / n

    if avg_neg >= avg_pos and avg_neg >= avg_neu:
        sent = "negative"
    elif avg_pos >= avg_neg and avg_pos >= avg_neu:
        sent = "positive"
    else:
        sent = "neutral"

    # Select evidence span from the most polarized chunk
    best_pred = max(predictions, key=lambda p: abs(p.p_neg - p.p_pos))

    return SentimentPrediction(
        sentiment=sent,
        p_pos=round(avg_pos, 4),
        p_neg=round(avg_neg, 4),
        p_neu=round(avg_neu, 4),
        evidence_span=best_pred.evidence_span,
    )


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def rule_based_sentiment_score(headline: str, body: str | None = None) -> SentimentScoreResult:
    """Deterministic, zero-dependency financial sentiment scorer and evidence extractor."""
    full_text = f"{headline}. {body or ''}".strip()
    sentences = split_into_sentences(full_text)

    neg_keywords = [
        "penalty",
        "penalties",
        "warning",
        "fine",
        "sebi",
        "show cause",
        "default",
        "resignation",
        "resigned",
        "downgrade",
        "downgraded",
        "loss",
        "fraud",
        "violation",
        "breach",
        "probe",
        "investigation",
    ]
    pos_keywords = [
        "win",
        "bags",
        "awarded",
        "profit up",
        "dividend",
        "expansion",
        "growth",
        "upgrade",
        "upgraded",
        "reaffirmed",
        "strong performance",
        "surpassed",
    ]

    best_evidence: str | None = None
    max_matches = 0
    neg_count = 0
    pos_count = 0

    for sentence in sentences:
        s_lower = sentence.lower()
        s_neg = sum(1 for kw in neg_keywords if kw in s_lower)
        s_pos = sum(1 for kw in pos_keywords if kw in s_lower)

        neg_count += s_neg
        pos_count += s_pos

        if (s_neg + s_pos) > max_matches:
            max_matches = s_neg + s_pos
            best_evidence = sentence

    if best_evidence is None and sentences:
        best_evidence = sentences[0]

    # Probabilities
    if neg_count > pos_count:
        p_neg = min(0.95, 0.60 + 0.10 * (neg_count - pos_count))
        p_neu = round((1.0 - p_neg) * 0.7, 4)
        p_pos = round(1.0 - p_neg - p_neu, 4)
        sentiment = "negative"
    elif pos_count > neg_count:
        p_pos = min(0.95, 0.60 + 0.10 * (pos_count - neg_count))
        p_neu = round((1.0 - p_pos) * 0.7, 4)
        p_neg = round(1.0 - p_pos - p_neu, 4)
        sentiment = "positive"
    else:
        p_neu = 0.80
        p_pos = 0.10
        p_neg = 0.10
        sentiment = "neutral"

    return SentimentScoreResult(
        model_name="prism_rule_sentiment",
        model_version="1.0.0",
        sentiment=sentiment,
        p_pos=round(p_pos, 4),
        p_neg=round(p_neg, 4),
        p_neu=round(p_neu, 4),
        evidence_span=best_evidence,
    )


def score_announcement_text(
    headline: str,
    body: str | None = None,
    config: dict[str, Any] | None = None,
) -> SentimentScoreResult:
    """Score text: FinBERT when enabled in config, rule-based fallback by default (D1)."""
    cfg = config or {}
    finbert_enabled = bool(cfg.get("finbert_enabled", False))

    if not finbert_enabled:
        return rule_based_sentiment_score(headline, body)

    # If FinBERT is explicitly enabled via config
    try:
        import torch  # type: ignore[import-not-found]
        from transformers import (  # type: ignore[import-not-found]
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        model_id = cfg.get("finbert_model_id", FINBERT_MODEL_ID)
        revision = cfg.get("finbert_revision", FINBERT_REVISION)

        tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        model = AutoModelForSequenceClassification.from_pretrained(model_id, revision=revision)
        model.eval()

        full_text = f"{headline}. {body or ''}".strip()
        inputs = tokenizer(
            full_text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_TOKENS,
            padding=True,
        )

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()

        # FinBERT labels: 0: positive, 1: negative, 2: neutral
        p_pos, p_neg, p_neu = probs[0], probs[1], probs[2]
        labels = ["positive", "negative", "neutral"]
        sentiment = labels[probs.index(max(probs))]

        sentences = split_into_sentences(full_text)
        evidence = sentences[0] if sentences else headline

        return SentimentScoreResult(
            model_name=f"finbert_{revision[:8]}",
            model_version=revision,
            sentiment=sentiment,
            p_pos=round(p_pos, 4),
            p_neg=round(p_neg, 4),
            p_neu=round(p_neu, 4),
            evidence_span=evidence,
        )
    except Exception as exc:
        logger.warning(
            "FinBERT requested but could not run (%s); falling back to rule-based scorer", exc
        )
        return rule_based_sentiment_score(headline, body)
