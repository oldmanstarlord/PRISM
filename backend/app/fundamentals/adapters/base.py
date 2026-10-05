"""Base protocol and types for corporate results ingestion adapters (FR-D9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol


@dataclass
class ParsedPeriod:
    """Standardized representation of a single fundamental reporting period."""

    period_end: date
    period_type: str  # "quarter" | "year"
    basis: str  # "consolidated" | "standalone" | "unknown"
    published_at: datetime
    published_at_method: str = "actual"  # "actual" | "estimated"
    revenue: float | None = None
    operating_profit: float | None = None
    pat: float | None = None
    interest_expense: float | None = None
    total_debt: float | None = None
    total_equity: float | None = None
    total_assets: float | None = None
    cash_from_operations: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Standardized representation of a source disclosure document."""

    source: str  # e.g. "YAHOO_FUNDAMENTALS", "CSV_IMPORT", "JSON_FIXTURE"
    doc_type: str  # "quarterly_results" | "annual_report"
    published_at: datetime
    published_at_method: str = "actual"  # "actual" | "estimated"
    content_hash: str = ""
    source_doc_id: str | None = None
    url: str | None = None
    raw_path: str | None = None
    periods: list[ParsedPeriod] = field(default_factory=list)


class ResultAdapter(Protocol):
    """Protocol for financial results ingestion adapters."""

    @property
    def source_tag(self) -> str:
        """Identifying tag for the source (e.g. YAHOO_FUNDAMENTALS)."""
        ...

    def fetch_results(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedDocument]:
        """Fetch and parse financial results for a given security."""
        ...
