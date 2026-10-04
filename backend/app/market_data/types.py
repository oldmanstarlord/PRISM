"""Typed values shared by the market-data component."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MarketInstrument:
    security_id: UUID
    symbol: str

    @property
    def yahoo_symbol(self) -> str:
        return f"{self.symbol}.NS"


@dataclass(frozen=True, slots=True)
class DailyPrice:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int
    dividend: Decimal = Decimal("0")
    stock_split: Decimal = Decimal("0")
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    severity: str
    message: str
    trade_date: date | None = None


@dataclass(frozen=True, slots=True)
class QualityResult:
    accepted: tuple[DailyPrice, ...]
    rejected_rows: int
    issues: tuple[QualityIssue, ...]

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)


@dataclass(slots=True)
class IngestionSummary:
    requested_symbols: int
    completed_symbols: int = 0
    failed_symbols: dict[str, str] = field(default_factory=dict)
    downloaded_rows: int = 0
    rejected_rows: int = 0
    raw_revisions_inserted: int = 0
    adjusted_inserted: int = 0
    adjusted_updated: int = 0
    corporate_actions_inserted: int = 0
    corporate_actions_updated: int = 0
    warnings: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "requested_symbols": self.requested_symbols,
            "completed_symbols": self.completed_symbols,
            "failed_symbols": self.failed_symbols,
            "downloaded_rows": self.downloaded_rows,
            "rejected_rows": self.rejected_rows,
            "raw_revisions_inserted": self.raw_revisions_inserted,
            "adjusted_inserted": self.adjusted_inserted,
            "adjusted_updated": self.adjusted_updated,
            "corporate_actions_inserted": self.corporate_actions_inserted,
            "corporate_actions_updated": self.corporate_actions_updated,
            "warnings": self.warnings,
        }
