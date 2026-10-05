"""Base protocol and types for governance ingestion adapters (FR-D9).

Every source of shareholding and insider-trade disclosures plugs in here.
The CSV adapter is the initial implementation; a live exchange adapter can
be added without changing the ingestion service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol


@dataclass
class ParsedShareholdingRecord:
    """One SEBI Reg 31 quarterly shareholding disclosure for a security."""

    quarter_end: date
    published_at: datetime  # Actual filing date — never estimated, never assumed
    promoter_pct: float | None = None
    promoter_pledged_pct_of_promoter: float | None = None
    fii_pct: float | None = None
    dii_pct: float | None = None
    public_pct: float | None = None
    source: str = "CSV_IMPORT"
    source_doc_id: str | None = None


@dataclass
class ParsedInsiderTradeRecord:
    """One SEBI PIT Reg 7(2) / SAST Reg 29/31 insider trade disclosure."""

    person_category: str
    txn_type: str  # buy | sell | pledge | revoke_pledge
    txn_date: date
    published_at: datetime  # Actual exchange acceptance date
    quantity: int | None = None
    value: float | None = None  # INR
    source: str = "CSV_IMPORT"
    source_doc_id: str | None = None


@dataclass
class ParsedShareholdingDocument:
    """Container for shareholding records fetched from one source batch."""

    source_tag: str
    records: list[ParsedShareholdingRecord] = field(default_factory=list)


@dataclass
class ParsedInsiderTradeDocument:
    """Container for insider trade records fetched from one source batch."""

    source_tag: str
    records: list[ParsedInsiderTradeRecord] = field(default_factory=list)


class ShareholdingAdapter(Protocol):
    """Protocol for quarterly shareholding pattern ingestion adapters."""

    @property
    def source_tag(self) -> str:
        """Identifying tag (e.g. CSV_IMPORT, NSE_FILING)."""
        ...

    def fetch_shareholding(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedShareholdingDocument]:
        """Return shareholding pattern records visible as of `as_of`."""
        ...


class InsiderTradeAdapter(Protocol):
    """Protocol for insider trade disclosure ingestion adapters."""

    @property
    def source_tag(self) -> str:
        """Identifying tag (e.g. CSV_IMPORT, NSE_PIT_FILING)."""
        ...

    def fetch_trades(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedInsiderTradeDocument]:
        """Return insider trade records visible as of `as_of`."""
        ...
