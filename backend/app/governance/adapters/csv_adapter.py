"""CSV / fixture-backed governance adapters (FR-D9).

SOURCE ACCESS ASSESSMENT (recorded as ASSUMPTION PD-8):
  - NSE India (nseindia.com) and BSE India (bseindia.com) publish shareholding-
    pattern and insider-trade disclosures as HTML/CSV downloadable pages.
  - Neither exchange offers a stable, authenticated REST API for public consumers.
  - Automated scraping is prohibited by exchange Terms of Service.
  - DECISION: Implement a file-import adapter backed by CSV fixtures.
    A live exchange or commercial-data adapter can be swapped in by implementing
    the ShareholdingAdapter / InsiderTradeAdapter protocol without changing
    the ingestion service (FR-D9).
  - published_at: stored from the filing metadata column in the CSV; never
    estimated or assumed. Files without a published_at column are rejected.

Expected CSV columns (shareholding):
  symbol, quarter_end, promoter_pct, promoter_pledged_pct_of_promoter,
  fii_pct, dii_pct, public_pct, published_at[, source_doc_id]

Expected CSV columns (insider trades):
  symbol, person_category, txn_type, quantity, value, txn_date,
  published_at[, source_doc_id]
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from typing import Any

from backend.app.governance.adapters.base import (
    ParsedInsiderTradeDocument,
    ParsedInsiderTradeRecord,
    ParsedShareholdingDocument,
    ParsedShareholdingRecord,
)

_DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]


def _parse_date(raw: str) -> date:

    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_datetime(raw: str) -> datetime:

    raw = raw.strip()
    # Try with timezone info first
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    # Fall back: try as date only → midnight UTC
    try:
        d = _parse_date(raw)

        return datetime(d.year, d.month, d.day, tzinfo=UTC)
    except ValueError:
        pass
    raise ValueError(f"Cannot parse datetime: {raw!r}")


def _opt_float(val: str | None) -> float | None:
    if val is None or val.strip() == "" or val.strip().lower() in ("na", "n/a", "none", "-"):
        return None
    return float(val.strip())


def _opt_int(val: str | None) -> int | None:
    if val is None or val.strip() == "" or val.strip().lower() in ("na", "n/a", "none", "-"):
        return None
    return int(float(val.strip()))


class CsvShareholdingAdapter:
    """Parse shareholding-pattern records from a CSV string or file path.

    The adapter can be initialised with:
      - csv_text: a raw CSV string (for fixtures / tests)
      - file_path: path to a CSV file on disk
    """

    def __init__(
        self,
        csv_text: str | None = None,
        file_path: str | None = None,
    ) -> None:
        if csv_text is None and file_path is None:
            raise ValueError("Either csv_text or file_path must be provided")
        self._csv_text = csv_text
        self._file_path = file_path

    @property
    def source_tag(self) -> str:
        return "CSV_IMPORT"

    def _read_text(self) -> str:
        if self._csv_text is not None:
            return self._csv_text
        assert self._file_path is not None
        with open(self._file_path, encoding="utf-8") as f:
            return f.read()

    def fetch_shareholding(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedShareholdingDocument]:
        """Parse all matching rows from the CSV filtered by symbol and as_of."""
        text = self._read_text()
        reader = csv.DictReader(io.StringIO(text))
        records: list[ParsedShareholdingRecord] = []
        for row in reader:
            row_sym = row.get("symbol", "").strip().upper()
            if row_sym != symbol.strip().upper():
                continue

            published_raw = row.get("published_at", "")
            if not published_raw.strip():
                raise ValueError(
                    f"Row for {symbol} has no published_at — real filing dates are mandatory (D4)."
                )
            published_at = _parse_datetime(published_raw)

            # Point-in-time: only include rows visible as of cutoff
            if as_of is not None and published_at > as_of:
                continue

            quarter_end = _parse_date(row["quarter_end"])
            rec = ParsedShareholdingRecord(
                quarter_end=quarter_end,
                published_at=published_at,
                promoter_pct=_opt_float(row.get("promoter_pct")),
                promoter_pledged_pct_of_promoter=_opt_float(
                    row.get("promoter_pledged_pct_of_promoter")
                ),
                fii_pct=_opt_float(row.get("fii_pct")),
                dii_pct=_opt_float(row.get("dii_pct")),
                public_pct=_opt_float(row.get("public_pct")),
                source=self.source_tag,
                source_doc_id=row.get("source_doc_id") or None,
            )
            records.append(rec)

        return [ParsedShareholdingDocument(source_tag=self.source_tag, records=records)]


class CsvInsiderTradeAdapter:
    """Parse insider trade disclosures from a CSV string or file path."""

    def __init__(
        self,
        csv_text: str | None = None,
        file_path: str | None = None,
    ) -> None:
        if csv_text is None and file_path is None:
            raise ValueError("Either csv_text or file_path must be provided")
        self._csv_text = csv_text
        self._file_path = file_path

    @property
    def source_tag(self) -> str:
        return "CSV_IMPORT"

    def _read_text(self) -> str:
        if self._csv_text is not None:
            return self._csv_text
        assert self._file_path is not None
        with open(self._file_path, encoding="utf-8") as f:
            return f.read()

    def fetch_trades(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedInsiderTradeDocument]:
        """Parse all matching rows from the CSV filtered by symbol and as_of."""
        text = self._read_text()
        reader = csv.DictReader(io.StringIO(text))
        records: list[ParsedInsiderTradeRecord] = []
        for row in reader:
            row_sym = row.get("symbol", "").strip().upper()
            if row_sym != symbol.strip().upper():
                continue

            published_raw = row.get("published_at", "")
            if not published_raw.strip():
                raise ValueError(
                    f"Row for {symbol} has no published_at — "
                    "real exchange acceptance dates are mandatory (D4)."
                )
            published_at = _parse_datetime(published_raw)

            # Point-in-time: only include rows visible as of cutoff
            if as_of is not None and published_at > as_of:
                continue

            txn_date = _parse_date(row["txn_date"])
            txn_type = row.get("txn_type", "").strip().lower()
            if txn_type not in {"buy", "sell", "pledge", "revoke_pledge"}:
                raise ValueError(
                    f"Unknown txn_type {txn_type!r} for {symbol}. "
                    "Allowed: buy, sell, pledge, revoke_pledge."
                )

            rec = ParsedInsiderTradeRecord(
                person_category=row.get("person_category", "unknown").strip(),
                txn_type=txn_type,
                txn_date=txn_date,
                published_at=published_at,
                quantity=_opt_int(row.get("quantity")),
                value=_opt_float(row.get("value")),
                source=self.source_tag,
                source_doc_id=row.get("source_doc_id") or None,
            )
            records.append(rec)

        return [ParsedInsiderTradeDocument(source_tag=self.source_tag, records=records)]


def _validate_shareholding_record(rec: ParsedShareholdingRecord) -> list[str]:
    """Return list of validation failure messages (empty = valid)."""
    errors: list[str] = []
    for field_name, val in [
        ("promoter_pct", rec.promoter_pct),
        ("fii_pct", rec.fii_pct),
        ("dii_pct", rec.dii_pct),
        ("public_pct", rec.public_pct),
        ("promoter_pledged_pct_of_promoter", rec.promoter_pledged_pct_of_promoter),
    ]:
        if val is not None and not (0.0 <= val <= 100.0):
            errors.append(f"{field_name}={val} is out of range [0, 100]")
    return errors


# Type alias for external callers
ShareholdingAdapterType = Any  # Protocol-compatible
InsiderTradeAdapterType = Any
