"""One score-to-label policy shared by regression evaluation and publication."""

from __future__ import annotations

from typing import cast

import numpy as np

SCORE_BANDS = [
    {"minimum": 0, "label": "Very Weak"},
    {"minimum": 40, "label": "Weak"},
    {"minimum": 60, "label": "Moderate"},
    {"minimum": 75, "label": "Strong"},
    {"minimum": 90, "label": "Very Strong"},
]
SCORE_DECIMALS = 2


def bounded_scores(predictions: np.ndarray) -> np.ndarray:
    """Round the bounded displayed score before choosing its category."""
    values = np.asarray(predictions, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Regression predictions must be finite one-dimensional scores")
    return cast(np.ndarray, np.round(np.clip(values, 0, 100), SCORE_DECIMALS))


def score_codes(scores: np.ndarray) -> np.ndarray:
    return cast(np.ndarray, np.digitize(bounded_scores(scores), [40, 60, 75, 90]).astype(int))
