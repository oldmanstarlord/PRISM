"""Base component protocol and value models for PRISM risk components (D2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ComponentValue:
    """Standardized output observation produced by a risk component for a single security."""

    security_id: UUID
    symbol: str
    component_id: str
    raw_value: float | None
    status: str  # ok | stale | missing | insufficient
    data_as_of: date | None
    data_age_days: int | None
    evidence_ref: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskContext:
    """Context and point-in-time cached data shared across risk components."""

    session: Any
    as_of: date
    data_cutoff: datetime
    config: dict[str, Any]
    cache: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Component(Protocol):
    """Protocol that every risk scoring component must implement (D2)."""

    key: str
    dimension: str
    direction: str  # higher_is_riskier | lower_is_riskier
    required_inputs: list[str]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],  # (security_id, symbol, industry)
        context: RiskContext,
    ) -> list[ComponentValue]:
        """Compute the component value for all securities in the universe point-in-time."""
        ...
