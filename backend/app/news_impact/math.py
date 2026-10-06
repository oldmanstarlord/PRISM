"""Pure, deterministic Step E4 scoring helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable


def recency_decay(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        raise ValueError("recency half-life must be positive")
    return float(0.5 ** (max(0.0, age_days) / half_life_days))


def path_exposure(
    severity: float,
    path_weight: float,
    decay: float,
    signal_strength: float = 1.0,
) -> float:
    """Severity/10 × path weight × recency decay × bounded signal strength."""
    values = (severity, path_weight, decay, signal_strength)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("exposure inputs must be finite")
    raw = (min(10.0, max(0.0, severity)) / 10.0) * max(0.0, path_weight)
    return min(1.0, max(0.0, raw * max(0.0, decay) * min(1.0, max(0.0, signal_strength))))


def exposure_band(score: float, medium_min: float, high_min: float) -> str:
    if not 0 <= medium_min <= high_min <= 1:
        raise ValueError("exposure bands must be ordered within [0, 1]")
    return "high" if score >= high_min else "medium" if score >= medium_min else "low"


def combine_exposures(scores: Iterable[float]) -> float:
    """Combine multiple paths with MAX to prevent double counting."""
    values = list(scores)
    return max(values, default=0.0)


def historical_reaction_label(n: int, minimum_analogues: int) -> str:
    if n < minimum_analogues:
        return f"insufficient history (n={n})"
    return f"historical reaction available (n={n})"


def spillover_is_eligible(r_squared: float, minimum_r_squared: float) -> bool:
    return math.isfinite(r_squared) and r_squared >= minimum_r_squared


def confidence_is_visible(confidence: float, minimum_confidence: float) -> bool:
    return confidence >= minimum_confidence


def affected_portfolio_weight(weights: Iterable[float]) -> float:
    return sum(weights)
