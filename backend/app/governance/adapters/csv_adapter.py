"""Strict manual-import adapters for official governance disclosure exports.

The operator downloads an official exchange export and maps it to the documented,
normalized columns. Every row is parsed before the job commits, so an unreadable
row aborts the batch. Production code never falls back to a fixture or web scrape.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from backend.app.governance.adapters.base import (
    ParsedInsiderTradeDocument,
    ParsedInsiderTradeRecord,
    ParsedShareholdingDocument,
    ParsedShareholdingRecord,
)

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")
_SHAREHOLDING_REQUIRED = {
    "symbol",
    "quarter_end",
    "promoter_pct",
    "promoter_pledged_pct_of_promoter",
    "fii_pct",
    "dii_pct",
    "public_pct",
    "published_at",
}
_INSIDER_REQUIRED = {
    "symbol",
    "person_category",
    "txn_type",
    "quantity",
    "value",
    "txn_date",
    "published_at",
}


def _parse_date(raw: str) -> date:
    clean = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"cannot parse date: {raw!r}")


def _parse_datetime(raw: str) -> datetime:
    clean = raw.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            value = datetime.strptime(clean, fmt)
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        except ValueError:
            continue
    parsed_date = _parse_date(clean)
    return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)


def _opt_float(value: str | None) -> float | None:
    if value is None or value.strip().lower() in {"", "na", "n/a", "none", "-"}:
        return None
    return float(value.strip())


def _opt_int(value: str | None) -> int | None:
    if value is None or value.strip().lower() in {"", "na", "n/a", "none", "-"}:
        return None
    parsed = float(value.strip().replace(",", ""))
    if not parsed.is_integer():
        raise ValueError(f"expected whole-number quantity, got {value!r}")
    return int(parsed)


def _validate_headers(
    fieldnames: Sequence[str] | None, required: set[str], dataset: str
) -> None:
    missing = required - set(fieldnames or [])
    if missing:
        raise ValueError(f"{dataset} CSV missing required columns: {sorted(missing)}")


def _validate_quarter_end(value: date) -> None:
    if (value.month, value.day) not in {(3, 31), (6, 30), (9, 30), (12, 31)}:
        raise ValueError(f"quarter_end {value.isoformat()} is not a calendar quarter end")


def _validate_shareholding_record(record: ParsedShareholdingRecord) -> list[str]:
    errors: list[str] = []
    percentages = {
        "promoter_pct": record.promoter_pct,
        "promoter_pledged_pct_of_promoter": record.promoter_pledged_pct_of_promoter,
        "fii_pct": record.fii_pct,
        "dii_pct": record.dii_pct,
        "public_pct": record.public_pct,
    }
    for field_name, value in percentages.items():
        if value is not None and not 0.0 <= value <= 100.0:
            errors.append(f"{field_name}={value} is outside [0, 100]")
    if record.shares_outstanding is not None and record.shares_outstanding <= 0:
        errors.append("shares_outstanding must be positive")
    return errors


class _StrictCsvAdapter:
    source_tag = "NSE_MANUAL_IMPORT"

    def __init__(self, csv_text: str | None = None, file_path: str | None = None) -> None:
        if csv_text is None and file_path is None:
            raise ValueError("either csv_text or file_path must be provided")
        self._csv_text = csv_text
        self._file_path = Path(file_path) if file_path else None

    def _read_text(self, dataset: str) -> str:
        if self._csv_text is not None:
            return self._csv_text
        assert self._file_path is not None
        if not self._file_path.is_file():
            raise FileNotFoundError(f"{dataset} export not found: {self._file_path}")
        return self._file_path.read_text(encoding="utf-8-sig")


class CsvShareholdingAdapter(_StrictCsvAdapter):
    def fetch_shareholding(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedShareholdingDocument]:
        del isin
        reader = csv.DictReader(io.StringIO(self._read_text("shareholding")))
        _validate_headers(reader.fieldnames, _SHAREHOLDING_REQUIRED, "shareholding")
        records: list[ParsedShareholdingRecord] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                if row.get("symbol", "").strip().upper() != symbol.strip().upper():
                    continue
                published_raw = row.get("published_at", "")
                if not published_raw.strip():
                    raise ValueError("actual published_at is mandatory (D4)")
                published_at = _parse_datetime(published_raw)
                if as_of is not None and published_at > as_of:
                    continue
                quarter_end = _parse_date(row["quarter_end"])
                _validate_quarter_end(quarter_end)
                record = ParsedShareholdingRecord(
                    quarter_end=quarter_end,
                    published_at=published_at,
                    promoter_pct=_opt_float(row.get("promoter_pct")),
                    promoter_pledged_pct_of_promoter=_opt_float(
                        row.get("promoter_pledged_pct_of_promoter")
                    ),
                    fii_pct=_opt_float(row.get("fii_pct")),
                    dii_pct=_opt_float(row.get("dii_pct")),
                    public_pct=_opt_float(row.get("public_pct")),
                    shares_outstanding=_opt_int(row.get("shares_outstanding")),
                    source=self.source_tag,
                    source_doc_id=row.get("source_doc_id") or None,
                )
                errors = _validate_shareholding_record(record)
                if errors:
                    raise ValueError("; ".join(errors))
                records.append(record)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"shareholding CSV row {row_number}: {exc}") from exc
        return [ParsedShareholdingDocument(source_tag=self.source_tag, records=records)]


class CsvInsiderTradeAdapter(_StrictCsvAdapter):
    def fetch_trades(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedInsiderTradeDocument]:
        del isin
        reader = csv.DictReader(io.StringIO(self._read_text("insider-trade")))
        _validate_headers(reader.fieldnames, _INSIDER_REQUIRED, "insider trade")
        records: list[ParsedInsiderTradeRecord] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                if row.get("symbol", "").strip().upper() != symbol.strip().upper():
                    continue
                published_raw = row.get("published_at", "")
                if not published_raw.strip():
                    raise ValueError("actual exchange published_at is mandatory (D4)")
                published_at = _parse_datetime(published_raw)
                if as_of is not None and published_at > as_of:
                    continue
                txn_type = row.get("txn_type", "").strip().lower()
                if txn_type not in {"buy", "sell", "pledge", "revoke_pledge"}:
                    raise ValueError(
                        f"unknown txn_type {txn_type!r}; allowed: buy, sell, pledge, revoke_pledge"
                    )
                record = ParsedInsiderTradeRecord(
                    person_category=row.get("person_category", "").strip(),
                    txn_type=txn_type,
                    txn_date=_parse_date(row["txn_date"]),
                    published_at=published_at,
                    quantity=_opt_int(row.get("quantity")),
                    value=_opt_float(row.get("value")),
                    source=self.source_tag,
                    source_doc_id=row.get("source_doc_id") or None,
                )
                if not record.person_category:
                    raise ValueError("person_category must be non-empty")
                if record.quantity is not None and record.quantity < 0:
                    raise ValueError("quantity must be non-negative")
                if record.value is not None and record.value < 0:
                    raise ValueError("value must be non-negative")
                records.append(record)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"insider trade CSV row {row_number}: {exc}") from exc
        return [ParsedInsiderTradeDocument(source_tag=self.source_tag, records=records)]


ShareholdingAdapterType = Any
InsiderTradeAdapterType = Any
