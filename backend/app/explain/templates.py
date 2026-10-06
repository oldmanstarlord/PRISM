"""Small fixed-template engine loaded exclusively from versioned model_config."""

from __future__ import annotations

from string import Formatter

from backend.app.explain.guardrails import validate_text
from backend.app.explain.schemas import ExplanationSentence


def build_sentence(
    template: str,
    values: dict[str, object],
    evidence_ids: list[str],
    config: dict[str, object],
) -> ExplanationSentence | None:
    """Render only when every placeholder and supporting evidence item exists."""
    if not evidence_ids:
        return None
    fields = [name for _, name, _, _ in Formatter().parse(template) if name]
    if any(field not in values or values[field] is None for field in fields):
        return None
    text = template.format(**values)
    validate_text(text, config)
    return ExplanationSentence(text=text, evidence_ids=evidence_ids)


def direction_label(direction: str) -> str:
    labels = {
        "higher_is_riskier": "higher values correspond to higher descriptive risk",
        "lower_is_riskier": "lower values correspond to higher descriptive risk",
    }
    return labels.get(direction, direction.replace("_", " "))
