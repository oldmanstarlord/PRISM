"""Benchmark adapter interface, CSV/Yahoo loaders, and validation (FR-D8, FR-D9)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

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
        self,
        benchmark_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
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

    Hardened to track and report unparseable rows, failing if bad rows exceed 0.5%.
    Supports ISO, DD-Mon-YYYY, DD Mon YYYY, and DD-MM-YYYY date formats.
    """

    source: str = "CSV"

    def __init__(self) -> None:
        self.total_rows: int = 0
        self.bad_rows: int = 0

    @staticmethod
    def parse_date(date_str: str) -> date:
        date_str = date_str.strip()
        # 1. ISO (YYYY-MM-DD)
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass

        # 2. DD-Mon-YYYY (e.g. 25-Sep-2026)
        try:
            return datetime.strptime(date_str, "%d-%b-%Y").date()
        except ValueError:
            pass

        # 3. DD Mon YYYY (e.g. 25 Sep 2026)
        try:
            return datetime.strptime(date_str, "%d %b %Y").date()
        except ValueError:
            pass

        # 4. DD-MM-YYYY (e.g. 25-09-2026)
        try:
            return datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            pass

        raise ValueError(f"Unparseable date: {date_str}")

    def parse_csv(self, csv_content: str | io.StringIO) -> list[BenchmarkPriceRecord]:
        """Parse CSV rows with columns: Date, Open, High, Low, Close, Volume."""
        if isinstance(csv_content, str):
            f = io.StringIO(csv_content)
        else:
            f = csv_content

        reader = csv.DictReader(f)
        records: list[BenchmarkPriceRecord] = []
        total_rows = 0
        bad_rows = 0

        for row in reader:
            total_rows += 1
            normalized = {
                k.strip().lower(): v.strip()
                for k, v in row.items()
                if k is not None and v is not None
            }

            date_str = (
                normalized.get("date")
                or normalized.get("trade_date")
                or normalized.get("historicaldate")
            )
            if not date_str:
                bad_rows += 1
                continue

            try:
                trade_date = self.parse_date(date_str)
            except Exception:
                bad_rows += 1
                continue

            try:
                close_str = normalized.get("close", "").replace(",", "")
                if not close_str:
                    bad_rows += 1
                    continue
                close_val = Decimal(close_str)
                if not close_val.is_finite() or close_val <= 0:
                    bad_rows += 1
                    continue
            except (InvalidOperation, ValueError):
                bad_rows += 1
                continue

            open_val = None
            if normalized.get("open"):
                try:
                    open_val = Decimal(normalized["open"].replace(",", ""))
                except (InvalidOperation, ValueError):
                    pass

            high_val = None
            if normalized.get("high"):
                try:
                    high_val = Decimal(normalized["high"].replace(",", ""))
                except (InvalidOperation, ValueError):
                    pass

            low_val = None
            if normalized.get("low"):
                try:
                    low_val = Decimal(normalized["low"].replace(",", ""))
                except (InvalidOperation, ValueError):
                    pass

            vol_val = None
            vol_str = normalized.get("volume", "").replace(",", "")
            if vol_str and vol_str.isdigit():
                vol_val = int(vol_str)

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

        self.total_rows = total_rows
        self.bad_rows = bad_rows

        if total_rows > 0:
            error_rate = bad_rows / total_rows
            if error_rate > 0.005:  # 0.5% tolerance threshold
                raise ValueError(
                    f"CSV benchmark import failed: {bad_rows} unparseable rows out of {total_rows} "
                    f"({error_rate:.2%}) exceeds 0.5% threshold"
                )

        return records

    def fetch_series(
        self,
        benchmark_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[BenchmarkPriceRecord]:
        raise NotImplementedError("CsvBenchmarkAdapter requires CSV content directly via parse_csv")


class YahooBenchmarkAdapter:
    """Benchmark adapter fetching NIFTY 200 series from Yahoo Finance (^CNX200) (FR-D8, FR-D9)."""

    source: str = "YAHOO"

    def __init__(self, symbol: str = "^CNX200") -> None:
        self.symbol = symbol

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    def fetch_raw_data(self) -> pd.DataFrame:
        ticker = yf.Ticker(self.symbol)
        df = ticker.history(period="max", interval="1d", auto_adjust=False)
        return df

    def parse_frame(
        self,
        frame: pd.DataFrame,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[BenchmarkPriceRecord]:
        if frame.empty or "Close" not in frame.columns:
            return []

        kolkata_tz = ZoneInfo("Asia/Kolkata")
        today_kolkata = datetime.now(kolkata_tz).date()

        records: list[BenchmarkPriceRecord] = []
        for timestamp, row in frame.iterrows():
            close_raw = row["Close"]
            if pd.isna(close_raw):
                continue

            try:
                close_dec = Decimal(str(close_raw))
            except (InvalidOperation, ValueError):
                continue

            if not close_dec.is_finite() or close_dec <= 0:
                continue

            ts = pd.Timestamp(timestamp)
            if ts.tzinfo is not None:
                trade_date = ts.tz_convert(kolkata_tz).date()
            else:
                trade_date = ts.date()

            # Always exclude today's date because today's bar may be partial
            if trade_date >= today_kolkata:
                continue

            if start_date and trade_date < start_date:
                continue
            if end_date and trade_date > end_date:
                continue

            vol_val = None
            if "Volume" in row and not pd.isna(row["Volume"]):
                try:
                    vol_val = int(row["Volume"])
                except (ValueError, TypeError):
                    vol_val = None

            records.append(
                BenchmarkPriceRecord(
                    trade_date=trade_date,
                    open=None,
                    high=None,
                    low=None,
                    close=close_dec,
                    volume=vol_val,
                )
            )

        return sorted(records, key=lambda r: r.trade_date)

    def fetch_series(
        self,
        benchmark_id: str = "NIFTY_200",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[BenchmarkPriceRecord]:
        frame = self.fetch_raw_data()
        return self.parse_frame(frame, start_date=start_date, end_date=end_date)


NIFTY_200_DESCRIPTION = (
    "NIFTY 200 PRICE index, single source Yahoo Finance ^CNX200 (unofficial), "
    "internally verified, not independently cross-checked."
)


def persist_benchmark_series(
    session: Session,
    benchmark_id: str,
    records: list[BenchmarkPriceRecord],
    source: str = "YAHOO",
    method_version: str = "official_daily_v1",
) -> tuple[int, list[str]]:
    """Validate and idempotently persist benchmark daily series."""
    # Ensure benchmark definition exists with updated description
    bench = session.scalar(
        select(BenchmarkDefinition).where(BenchmarkDefinition.benchmark_id == benchmark_id)
    )
    desc_val = (
        NIFTY_200_DESCRIPTION
        if benchmark_id == "NIFTY_200"
        else f"{benchmark_id} benchmark series."
    )

    if bench is None:
        bench = BenchmarkDefinition(
            benchmark_id=benchmark_id,
            name=f"{benchmark_id} Index",
            description=desc_val,
            currency="INR",
            source=source,
        )
        session.add(bench)
        session.flush()
    else:
        if bench.description != desc_val:
            bench.description = desc_val
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
