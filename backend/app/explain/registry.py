"""Registry and protocol for adding explainers without changing shared services."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from backend.app.explain.evidence import Evidence
from backend.app.explain.schemas import ExplanationPayload


@runtime_checkable
class Explainer(Protocol):
    subject_type: str

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]: ...

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload: ...


class ExplainerRegistry:
    def __init__(self) -> None:
        self._explainers: dict[str, Explainer] = {}

    def register(self, explainer: Explainer) -> None:
        if explainer.subject_type in self._explainers:
            raise ValueError(f"explainer already registered: {explainer.subject_type}")
        self._explainers[explainer.subject_type] = explainer

    def get(self, subject_type: str) -> Explainer:
        try:
            return self._explainers[subject_type]
        except KeyError as exc:
            raise LookupError(f"no explainer registered for {subject_type}") from exc


registry = ExplainerRegistry()
