"""Event importance calculation engine (SRS OQ-9, D1, D3)."""

from __future__ import annotations

from typing import Any

DEFAULT_IMPORTANCE_WEIGHTS: dict[str, float] = {
    "regulatory_action": 10.0,
    "debt_rating": 8.5,
    "results": 8.0,
    "management_change": 7.0,
    "promoter_insider": 6.5,
    "ma_order": 5.0,
    "dividend": 3.0,
    "other": 2.0,
}

DEFAULT_MAGNITUDE_MULTIPLIERS: dict[str, float] = {
    "auditor_resignation": 1.5,
    "ceo_resignation": 1.3,
    "cfo_resignation": 1.3,
    "credit_downgrade": 1.4,
    "credit_upgrade": 1.0,
    "default": 2.0,
    "regulatory_penalty": 1.5,
    "standard": 1.0,
}


def parse_event_magnitude(headline: str, body: str | None = None) -> tuple[float, str]:
    """Parse quantifiable magnitude or critical keywords from announcement text."""
    combined = (headline + " " + (body or "")).lower()

    if "default" in combined or "delay in debt servicing" in combined:
        return DEFAULT_MAGNITUDE_MULTIPLIERS["default"], "debt_default_detected"

    if "auditor" in combined and ("resignation" in combined or "resigned" in combined):
        return DEFAULT_MAGNITUDE_MULTIPLIERS["auditor_resignation"], "auditor_resignation_detected"

    if "penalty" in combined or "fine" in combined or "monetary penalty" in combined:
        return DEFAULT_MAGNITUDE_MULTIPLIERS["regulatory_penalty"], "monetary_penalty_detected"

    if "downgrade" in combined or "downgraded" in combined:
        return DEFAULT_MAGNITUDE_MULTIPLIERS["credit_downgrade"], "credit_downgrade_detected"

    if ("cfo" in combined or "chief financial officer" in combined) and (
        "resignation" in combined or "resigned" in combined
    ):
        return DEFAULT_MAGNITUDE_MULTIPLIERS["cfo_resignation"], "cfo_resignation_detected"

    if ("ceo" in combined or "chief executive officer" in combined) and (
        "resignation" in combined or "resigned" in combined
    ):
        return DEFAULT_MAGNITUDE_MULTIPLIERS["ceo_resignation"], "ceo_resignation_detected"

    return DEFAULT_MAGNITUDE_MULTIPLIERS["standard"], "standard_magnitude"


def calculate_event_importance(
    event_type: str,
    headline: str,
    body: str | None = None,
    weights_config: dict[str, float] | None = None,
    multipliers_config: dict[str, float] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Calculate normalized event importance score in [1.0, 10.0] pts (Resolves SRS OQ-9).

    Formula:
        importance = min(10.0, max(1.0, base_weight * magnitude_multiplier))
    """
    weights = weights_config or DEFAULT_IMPORTANCE_WEIGHTS
    base_weight = weights.get(event_type, weights.get("other", 2.0))

    multiplier, magnitude_rationale = parse_event_magnitude(headline, body)

    raw_score = base_weight * multiplier
    normalized_importance = round(min(10.0, max(1.0, raw_score)), 2)

    components: dict[str, Any] = {
        "event_type": event_type,
        "base_weight": base_weight,
        "magnitude_multiplier": multiplier,
        "magnitude_rationale": magnitude_rationale,
        "raw_score": round(raw_score, 2),
        "normalized_importance": normalized_importance,
        "formula": "min(10.0, max(1.0, base_weight * magnitude_multiplier))",
    }

    return normalized_importance, components
