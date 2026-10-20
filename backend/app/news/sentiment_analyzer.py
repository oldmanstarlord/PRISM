"""Financial sentiment analysis with FinBERT transformer and transparent lexicon baseline."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from backend.app.news.schemas import SentimentLabel

logger = logging.getLogger(__name__)

# Transparent Loughran-McDonald inspired financial dictionary
FINANCIAL_LEXICON_POSITIVE = {
    "surge", "surges", "jump", "jumps", "gain", "gains", "growth", "grow", "profit",
    "profits", "profitable", "expansion", "record", "beat", "beats", "outperform",
    "dividend", "upgrade", "upgrades", "rally", "rallies", "resilient", "strong",
    "bullish", "breakthrough", "milestone", "advances", "optimism",
}

FINANCIAL_LEXICON_NEGATIVE = {
    "slump", "slumps", "plunge", "plunges", "loss", "losses", "decline", "declines",
    "drop", "drops", "penalty", "fine", "litigation", "lawsuit", "fraud", "default",
    "downgrade", "downgrades", "investigation", "probe", "debt", "crisis", "weak",
    "weakness", "bearish", "curb", "deficit", "scandal", "violation", "scrutiny",
}

FINANCIAL_LEXICON_UNCERTAIN = {
    "uncertain", "uncertainty", "pending", "volatile", "volatility", "contingent",
    "speculation", "unclear", "mixed", "cautious", "downturn", "exposure",
}


class SentimentAnalyzer:
    """Analyzes financial news sentiment using FinBERT with transparent lexicon fallback."""

    def __init__(self, use_transformer: bool = True) -> None:
        self.use_transformer = use_transformer
        self._transformer_pipeline: Any = None
        self._pipeline_init_attempted: bool = False

    def _get_transformer_pipeline(self) -> Any:
        """Lazily initialize transformer pipeline with graceful error handling."""
        if not self.use_transformer:
            return None
        if not self._pipeline_init_attempted:
            self._pipeline_init_attempted = True
            try:
                from transformers import pipeline

                # Use ProsusAI/finbert (CPU/GPU-agnostic with top_k=None)
                self._transformer_pipeline = pipeline(
                    "text-classification",
                    model="ProsusAI/finbert",
                    top_k=None,
                    device=-1,  # CPU by default for stability
                )
                logger.info("FinBERT transformer pipeline successfully initialized.")
            except Exception as e:
                logger.warning(
                    "FinBERT download/init unavailable (%s); using transparent lexicon fallback.",
                    e,
                )
                self._transformer_pipeline = None
        return self._transformer_pipeline

    def analyze_lexicon_baseline(self, text: str) -> dict[str, Any]:
        """Transparent, rule-based lexicon baseline scoring."""
        t_start = time.perf_counter()
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

        pos_count = sum(1 for w in words if w in FINANCIAL_LEXICON_POSITIVE)
        neg_count = sum(1 for w in words if w in FINANCIAL_LEXICON_NEGATIVE)
        unc_count = sum(1 for w in words if w in FINANCIAL_LEXICON_UNCERTAIN)

        total_polarized = pos_count + neg_count

        if total_polarized == 0:
            if unc_count > 0:
                label: SentimentLabel = "uncertain"
                score = 0.0
                confidence = 0.60
            else:
                label = "neutral"
                score = 0.0
                confidence = 0.70
        elif unc_count > 0 and unc_count >= total_polarized:
            # When uncertainty terms equal or outnumber polarized terms
            label = "uncertain"
            score = 0.0
            confidence = 0.50
        else:
            raw_score = (pos_count - neg_count) / (total_polarized + 1.0)
            score = round(max(-1.0, min(1.0, raw_score * 1.5)), 4)
            margin = abs(pos_count - neg_count) / total_polarized
            confidence = round(min(0.95, 0.50 + 0.40 * margin), 4)

            # Strict threshold for low-confidence classifications
            if confidence < 0.55:
                label = "uncertain"
            elif score > 0.15:
                label = "positive"
            elif score < -0.15:
                label = "negative"
            else:
                label = "neutral"

        t_elapsed = (time.perf_counter() - t_start) * 1000.0

        return {
            "sentiment_score": score,
            "sentiment_label": label,
            "sentiment_confidence": confidence,
            "model_name": "lexicon-financial-v1",
            "model_version": "2026.1",
            "processing_time_ms": round(t_elapsed, 2),
        }

    def analyze(self, text: str) -> dict[str, Any]:
        """Score sentiment using FinBERT transformer if available, or lexicon fallback."""
        pipe = self._get_transformer_pipeline()
        if pipe is None:
            return self.analyze_lexicon_baseline(text)

        t_start = time.perf_counter()
        try:
            outputs = pipe(text[:512])  # Truncate to maximum sequence length
            t_elapsed = (time.perf_counter() - t_start) * 1000.0

            raw_results: Any = (
                outputs[0]
                if isinstance(outputs, list) and outputs and isinstance(outputs[0], list)
                else outputs
            )
            scores_by_label: dict[str, float] = {}
            if isinstance(raw_results, list):
                for item in raw_results:
                    if isinstance(item, dict) and "label" in item and "score" in item:
                        scores_by_label[str(item["label"]).lower()] = float(item["score"])

            p_pos = scores_by_label.get("positive", 0.0)
            p_neg = scores_by_label.get("negative", 0.0)
            p_neu = scores_by_label.get("neutral", 0.0)

            # Polarity score on [-1.0, 1.0] scale
            polarity = round(p_pos - p_neg, 4)
            top_prob = max(p_pos, p_neg, p_neu)

            # Strict low-confidence uncertainty governance
            if top_prob < 0.55:
                label: SentimentLabel = "uncertain"
            elif p_pos > max(p_neg, p_neu):
                label = "positive"
            elif p_neg > max(p_pos, p_neu):
                label = "negative"
            else:
                label = "neutral"

            return {
                "sentiment_score": polarity,
                "sentiment_label": label,
                "sentiment_confidence": round(top_prob, 4),
                "model_name": "finbert-transformer-v1",
                "model_version": "2026.1",
                "processing_time_ms": round(t_elapsed, 2),
            }
        except Exception as e:
            logger.warning("FinBERT inference failed (%s); reverting to lexicon baseline.", e)
            return self.analyze_lexicon_baseline(text)
