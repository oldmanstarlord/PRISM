"""Tests for text chunking, aggregation, rule-based fallback, and FinBERT (Step 10)."""

from __future__ import annotations

from backend.app.events.finbert import (
    SentimentPrediction,
    aggregate_chunk_predictions,
    chunk_text,
    score_announcement_text,
)


def test_chunk_text_boundaries() -> None:
    """Chunking splits long documents into token-bounded segments with overlap."""
    # 1. Short text stays in one chunk
    short_text = "TCS announces strategic partnership with AWS for cloud modernization."
    chunks = chunk_text(short_text, max_tokens=100)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    # 2. Empty text returns empty list
    assert chunk_text("", max_tokens=100) == []
    assert chunk_text("   ", max_tokens=100) == []

    # 3. Long text chunking with overlap
    words = [f"word{i}" for i in range(250)]
    long_doc = ". ".join([" ".join(words[i : i + 20]) for i in range(0, 250, 20)])
    chunks_long = chunk_text(long_doc, max_tokens=50, overlap_tokens=10)
    assert len(chunks_long) > 1


def test_hand_calculated_aggregation() -> None:
    """Hand-calculated test for chunk prediction aggregation."""
    # Two chunks:
    # Chunk 1: negative (pos=0.1, neg=0.8, neu=0.1)
    # Chunk 2: neutral (pos=0.1, neg=0.2, neu=0.7)
    chunks = [
        SentimentPrediction(
            sentiment="negative",
            p_pos=0.10,
            p_neg=0.80,
            p_neu=0.10,
            evidence_span="Penalty was imposed by the regulatory board.",
        ),
        SentimentPrediction(
            sentiment="neutral",
            p_pos=0.10,
            p_neg=0.20,
            p_neu=0.70,
            evidence_span="The meeting commenced at 10 AM.",
        ),
    ]

    # Weighted average:
    # p_pos = (0.10 + 0.10) / 2 = 0.10
    # p_neg = (0.80 + 0.20) / 2 = 0.50
    # p_neu = (0.10 + 0.70) / 2 = 0.40
    # Highest is p_neg (0.50) -> sentiment = negative
    # Evidence span is the most polarized chunk (neg=0.80 vs neg=0.20)
    agg = aggregate_chunk_predictions(chunks, method="weighted_average")
    assert agg.sentiment == "negative"
    assert round(agg.p_pos, 4) == 0.10
    assert round(agg.p_neg, 4) == 0.50
    assert round(agg.p_neu, 4) == 0.40
    assert "Penalty was imposed" in agg.evidence_span


def test_rule_based_sentiment_fallback() -> None:
    """Zero-dependency deterministic classifier detects positive, negative, and neutral keywords."""
    cfg = {"finbert_enabled": False}

    # Negative case: penalty
    res_neg = score_announcement_text(
        "RBI imposes monetary penalty of Rs 12 Crore for non-compliance",
        config=cfg,
    )
    assert res_neg.sentiment == "negative"
    assert res_neg.p_neg > res_neg.p_pos

    # Positive case: contract win
    res_pos = score_announcement_text(
        "TCS bags contract valued at 1 billion USD from UK pension scheme",
        config=cfg,
    )
    assert res_pos.sentiment == "positive"
    assert res_pos.p_pos > res_pos.p_neg

    # Neutral case: standard AGM notice
    res_neu = score_announcement_text(
        "Notice of 30th Annual General Meeting and Book Closure Date",
        config=cfg,
    )
    assert res_neu.sentiment == "neutral"
    assert res_neu.p_neu > res_neu.p_pos
    assert res_neu.p_neu > res_neg.p_pos
