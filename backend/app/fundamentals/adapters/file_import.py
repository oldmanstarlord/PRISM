"""File and fixture import adapters for quarterly and annual corporate results (FR-D9)."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from backend.app.fundamentals.adapters.base import ParsedDocument, ParsedPeriod, ResultAdapter


def _parse_flt(row: dict[str, str], key: str) -> float | None:
    val = row.get(key)
    if val is None or val.strip() == "":
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


class CsvResultAdapter(ResultAdapter):
    """Adapter importing results from standardized CSV files."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    @property
    def source_tag(self) -> str:
        return "CSV_IMPORT"

    def fetch_results(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedDocument]:
        if not self.file_path.exists():
            return []

        content = self.file_path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()

        periods: list[ParsedPeriod] = []
        with open(self.file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("symbol", "").strip() != symbol:
                    continue

                period_end = date.fromisoformat(row["period_end"].strip())
                pub_str = row.get("published_at")
                if pub_str:
                    published_at = datetime.fromisoformat(pub_str).replace(tzinfo=UTC)
                    method = row.get("published_at_method", "actual")
                else:
                    # fallback
                    published_at = datetime(
                        period_end.year, period_end.month, period_end.day, 18, 0, tzinfo=UTC
                    )
                    method = "estimated"

                extra_raw = row.get("extra")
                extra: dict[str, Any] = {}
                if extra_raw:
                    try:
                        extra = json.loads(extra_raw)
                    except Exception:
                        pass

                period = ParsedPeriod(
                    period_end=period_end,
                    period_type=row.get("period_type", "quarter").strip(),
                    basis=row.get("basis", "consolidated").strip(),
                    published_at=published_at,
                    published_at_method=method,
                    revenue=_parse_flt(row, "revenue"),
                    operating_profit=_parse_flt(row, "operating_profit"),
                    pat=_parse_flt(row, "pat"),
                    interest_expense=_parse_flt(row, "interest_expense"),
                    total_debt=_parse_flt(row, "total_debt"),
                    total_equity=_parse_flt(row, "total_equity"),
                    total_assets=_parse_flt(row, "total_assets"),
                    cash_from_operations=_parse_flt(row, "cash_from_operations"),
                    extra=extra,
                )
                periods.append(period)

        if not periods:
            return []

        doc = ParsedDocument(
            source=self.source_tag,
            doc_type="quarterly_results",
            published_at=max(p.published_at for p in periods),
            published_at_method="actual"
            if all(p.published_at_method == "actual" for p in periods)
            else "estimated",
            content_hash=content_hash,
            raw_path=str(self.file_path),
            periods=periods,
        )
        return [doc]


class JsonResultAdapter(ResultAdapter):
    """Adapter importing results from structured JSON files or fixture dictionaries."""

    def __init__(self, data_or_path: str | Path | list[dict[str, Any]]) -> None:
        self.raw_path: str | None
        self.content: bytes
        self.data: list[dict[str, Any]]

        if isinstance(data_or_path, (str, Path)):
            path = Path(data_or_path)
            if path.exists():
                self.content = path.read_bytes()
                self.data = json.loads(self.content.decode("utf-8"))
                self.raw_path = str(path)
            else:
                self.content = b"[]"
                self.data = []
                self.raw_path = None
        else:
            self.data = data_or_path
            self.content = json.dumps(data_or_path, sort_keys=True).encode("utf-8")
            self.raw_path = None

    @property
    def source_tag(self) -> str:
        return "JSON_FIXTURE"

    def fetch_results(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedDocument]:
        items = [item for item in self.data if item.get("symbol") == symbol]
        if not items:
            return []

        periods: list[ParsedPeriod] = []
        for item in items:
            for p_dict in item.get("periods", []):
                period_end = date.fromisoformat(p_dict["period_end"])
                pub_str = p_dict.get("published_at")
                if pub_str:
                    published_at = datetime.fromisoformat(pub_str).replace(tzinfo=UTC)
                    method = p_dict.get("published_at_method", "actual")
                else:
                    published_at = datetime(
                        period_end.year, period_end.month, period_end.day, 18, 0, tzinfo=UTC
                    )
                    method = "estimated"

                period = ParsedPeriod(
                    period_end=period_end,
                    period_type=p_dict.get("period_type", "quarter"),
                    basis=p_dict.get("basis", "consolidated"),
                    published_at=published_at,
                    published_at_method=method,
                    revenue=p_dict.get("revenue"),
                    operating_profit=p_dict.get("operating_profit"),
                    pat=p_dict.get("pat"),
                    interest_expense=p_dict.get("interest_expense"),
                    total_debt=p_dict.get("total_debt"),
                    total_equity=p_dict.get("total_equity"),
                    total_assets=p_dict.get("total_assets"),
                    cash_from_operations=p_dict.get("cash_from_operations"),
                    extra=p_dict.get("extra", {}),
                )
                periods.append(period)

        if not periods:
            return []

        content_hash = hashlib.sha256(self.content).hexdigest()
        doc = ParsedDocument(
            source=self.source_tag,
            doc_type="quarterly_results",
            published_at=max(p.published_at for p in periods),
            published_at_method="actual"
            if all(p.published_at_method == "actual" for p in periods)
            else "estimated",
            content_hash=content_hash,
            raw_path=self.raw_path,
            periods=periods,
        )
        return [doc]
