"""Deterministic language and evidence guardrails for explanations."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from backend.app.explain.schemas import ExplanationPayload, ExplanationSentence


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase.lower())}\b", text.lower()) is not None


def validate_text(text: str, config: dict[str, object]) -> None:
    banned = config.get("banned_phrases", [])
    if not isinstance(banned, list):
        raise ValueError("explain template banned_phrases must be a list")
    for phrase in banned:
        if isinstance(phrase, str) and _contains_phrase(text, phrase):
            raise ValueError(f"explanation contains banned phrase: {phrase}")
    lowered = text.lower()
    if "correlation" in lowered or "correlated" in lowered:
        required = config.get("correlation_required_phrase")
        if not isinstance(required, str) or required.lower() not in lowered:
            raise ValueError(
                "correlation wording must use the configured 'moves together with' language"
            )


def evidence_bound_sentences(
    sentences: Iterable[ExplanationSentence],
    valid_evidence_ids: set[str],
    config: dict[str, object],
) -> list[ExplanationSentence]:
    """Drop unsupported sentences and fail closed on unsafe supported text."""
    output: list[ExplanationSentence] = []
    for sentence in sentences:
        if not sentence.evidence_ids:
            continue
        if any(evidence_id not in valid_evidence_ids for evidence_id in sentence.evidence_ids):
            continue
        validate_text(sentence.text, config)
        output.append(sentence)
    return output


def apply_payload_guardrails(
    payload: ExplanationPayload, config: dict[str, Any]
) -> ExplanationPayload:
    """Fail closed on unsafe text and attach the configured mandatory notices."""
    validate_text(payload.headline, config)
    valid_ids = {item.evidence_id for item in payload.evidence}
    limitations = config.get("limitations")
    disclaimer = config.get("disclaimer")
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        raise ValueError("explain template limitations must be a string list")
    if not limitations:
        raise ValueError("explain template limitations must not be empty")
    if not isinstance(disclaimer, str) or not disclaimer.strip():
        raise ValueError("explain template disclaimer must not be empty")
    sections = [
        section.model_copy(
            update={"sentences": evidence_bound_sentences(section.sentences, valid_ids, config)}
        )
        for section in payload.sections
    ]
    confidence = payload.confidence.model_copy(
        update={"reasons": evidence_bound_sentences(payload.confidence.reasons, valid_ids, config)}
    )
    combined_limitations = list(dict.fromkeys([*limitations, *payload.limitations]))
    return payload.model_copy(
        update={
            "summary_points": evidence_bound_sentences(payload.summary_points, valid_ids, config),
            "sections": sections,
            "confidence": confidence,
            "limitations": combined_limitations,
            "disclaimer": disclaimer,
        }
    )
