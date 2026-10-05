"""Benchmark adapter interface, CSV loader, and validation for index series (FR-D8, FR-D9)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import BenchmarkDefinition, BenchmarkSeries


@dataclass(frozen=True, slots=True)
class BenchmarkPriceRecord:
    """Daily benchmark price observation."""

    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    volume: int | None = None


@runtime_checkable
class BenchmarkAdapter(Protocol):
    """Replaceable adapter interface for benchmark index series (FR-D9)."""

    def fetch_series(
        self, benchmark_id: str, start_date: date, end_date: date
    ) -> list[BenchmarkPriceRecord]:
        """Fetch historical daily observations for the specified benchmark."""
        ...


def validate_benchmark_records(
    records: list[BenchmarkPriceRecord],
) -> tuple[list[BenchmarkPriceRecord], list[str]]:
    """Validate benchmark observations:
    checks duplicates, non-positive close, invalid high/low, extreme returns.
    """
    accepted: list[BenchmarkPriceRecord] = []
    issues: list[str] = []
    seen_dates: set[date] = set()
    prev_close: Decimal | None = None

    for rec in sorted(records, key=lambda r: r.trade_date):
        if rec.trade_date in seen_dates:
            issues.append(f"duplicate_date:{rec.trade_date}")
            continue
        seen_dates.add(rec.trade_date)

        if not rec.close.is_finite() or rec.close <= 0:
            issues.append(f"invalid_close:{rec.trade_date}")
            continue

        if rec.high is not None and rec.low is not None and rec.high < rec.low:
            issues.append(f"high_less_than_low:{rec.trade_date}")
            continue

        if prev_close is not None and prev_close > 0:
            ret = abs((rec.close - prev_close) / prev_close)
            # Index moves > 15% in a single day are flagged as extreme
            if ret > Decimal("0.15"):
                issues.append(f"extreme_index_return:{rec.trade_date}:{ret:.4f}")

        prev_close = rec.close
        accepted.append(rec)

    return accepted, issues


class CsvBenchmarkAdapter:
    """Adapter reading official Nifty Indices daily CSV exports or standardized fixtures.

    Research note on terms and rate limits:
    Official NSE/Nifty Indices does not provide an open programmatic REST API with public SLA.
    Downloading requires interactive session tokens or manual CSV export. To comply with terms
    and avoid brittle web scraping, this adapter ingests verified CSV archives.
    """

    def parse_csv(self, csv_content: str | io.StringIO) -> list[BenchmarkPriceRecord]:
        """Parse CSV rows with columns: Date, Open, High, Low, Close, Volume."""
        if isinstance(csv_content, str):
            f = io.StringIO(csv_content)
        else:
            f = csv_content

        reader = csv.DictReader(f)
        records: list[BenchmarkPriceRecord] = []

        for row in reader:
            # Normalize column names (strip whitespace and lower-case)
            normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            date_str = (
                normalized.get("date")
                or normalized.get("trade_date")
                or normalized.get("historicaldate")
            )
            if not date_str:
                continue

            try:
                # Handle YYYY-MM-DD or DD-Mon-YYYY or DD-MM-YYYY
                if "-" in date_str:
                    parts = date_str.split("-")
                    if len(parts[0]) == 4:
                        trade_date = date.fromisoformat(date_str)
                    else:
                        trade_date = datetime.strptime(date_str, "%d-%b-%Y").date()
                else:
                    trade_date = date.fromisoformat(date_str)
            except Exception:
                continue

            try:
                close_val = Decimal(normalized.get("close", "0").replace(",", ""))
                open_val = (
                    Decimal(normalized["open"].replace(",", "")) if normalized.get("open") else None
                )
                high_val = (
                    Decimal(normalized["high"].replace(",", "")) if normalized.get("high") else None
                )
                low_val = (
                    Decimal(normalized["low"].replace(",", "")) if normalized.get("low") else None
                )
                vol_str = normalized.get("volume", "").replace(",", "")
                vol_val = int(vol_str) if vol_str and vol_str.isdigit() else None
            except (InvalidOperation, ValueError):
                continue

            records.append(
                BenchmarkPriceRecord(
                    trade_date=trade_date,
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    volume=vol_val,
                )
            )

        return records


def persist_benchmark_series(
    session: Session,
    benchmark_id: str,
    records: list[BenchmarkPriceRecord],
    source: str = "NIFTY_INDICES_CSV",
    method_version: str = "official_daily_v1",
) -> tuple[int, list[str]]:
    """Validate and idempotently persist benchmark daily series."""
    # Ensure benchmark definition exists
    bench = session.scalar(
        select(BenchmarkDefinition).where(BenchmarkDefinition.benchmark_id == benchmark_id)
    )
    if bench is None:
        bench = BenchmarkDefinition(
            benchmark_id=benchmark_id,
            name=f"{benchmark_id} Index",
            currency="INR",
            source=source,
        )
        session.add(bench)
        session.flush()

    valid_records, issues = validate_benchmark_records(records)
    if not valid_records:
        return 0, issues

    # Load existing dates for this benchmark and source
    existing_dates = set(
        session.scalars(
            select(BenchmarkSeries.trade_date).where(
                BenchmarkSeries.benchmark_id == benchmark_id,
                BenchmarkSeries.source == source,
            )
        ).all()
    )

    now = datetime.now(UTC)
    inserted = 0
    for rec in valid_records:
        if rec.trade_date in existing_dates:
            continue
        series_row = BenchmarkSeries(
            benchmark_id=benchmark_id,
            trade_date=rec.trade_date,
            open=rec.open,
            high=rec.high,
            low=rec.low,
            close=rec.close,
            volume=rec.volume,
            source=source,
            source_revision=1,
            method_version=method_version,
            ingested_at=now,
            quality_flags={},
        )
        session.add(series_row)
        inserted += 1

    session.flush()
    return inserted, issues
