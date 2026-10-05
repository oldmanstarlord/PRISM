"""Base protocol and data contracts for macroeconomic series adapters (FR-D9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class ParsedObservation:
    """Standardized point-in-time macroeconomic observation."""

    series_key: str
    obs_date: date
    value: float
    published_at: datetime
    ingested_at: datetime
    version: int = 1


class MacroSeriesAdapter(Protocol):
    """Adapter interface for fetching macroeconomic time series."""

    @property
    def source_name(self) -> str:
        """Identifying name of the data provider adapter."""
        ...

    def fetch_observations(
        self,
        series_key: str,
        start_date: date | None = None,
        end_date: date | None = None,
        cutoff: datetime | None = None,
    ) -> list[ParsedObservation]:
        """Fetch observations for a given series key."""
        ...
