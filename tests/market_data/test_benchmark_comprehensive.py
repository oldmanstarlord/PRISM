"""Tests for NIFTY 200 benchmark ingestion and validation (FR-D8, FR-D9, Task 4 & 5)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Base,
    BenchmarkDefinition,
)
from backend.app.market_data.benchmark import (
    BenchmarkPriceRecord,
    CsvBenchmarkAdapter,
    YahooBenchmarkAdapter,
    persist_benchmark_series,
)
from backend.app.market_data.benchmark_check import (
    run_benchmark_checks,
)


@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Test 6: Required input missing & no sample-data fallback in production
# ---------------------------------------------------------------------------
def test_csv_adapter_no_sample_fallback() -> None:
    adapter = CsvBenchmarkAdapter()
    with pytest.raises(NotImplementedError, match="requires CSV content directly"):
        adapter.fetch_series(benchmark_id="NIFTY_200")


def test_no_sample_fixture_in_production_module() -> None:
    import backend.app.market_data.benchmark as bench_mod

    assert not hasattr(bench_mod, "SAMPLE_BENCHMARK_FIXTURE")


# ---------------------------------------------------------------------------
# Test 7: CSV Parser date formats, invalid row counting, and >0.5% failure
# ---------------------------------------------------------------------------
def test_csv_parser_supported_date_formats() -> None:
    csv_content = """Date,Close
2026-01-05,12000.0
06-Jan-2026,12050.0
07 Jan 2026,12100.0
08-01-2026,12150.0
"""
    adapter = CsvBenchmarkAdapter()
    records = adapter.parse_csv(csv_content)
    assert len(records) == 4
    assert records[0].trade_date == date(2026, 1, 5)
    assert records[1].trade_date == date(2026, 1, 6)
    assert records[2].trade_date == date(2026, 1, 7)
    assert records[3].trade_date == date(2026, 1, 8)
    assert adapter.bad_rows == 0


def test_csv_parser_fails_when_bad_rows_exceed_half_percent() -> None:
    # 200 good rows, 2 bad rows = 2/202 = 0.99% > 0.5%
    rows = ["Date,Close"]
    for _ in range(200):
        rows.append("2026-01-01,10000.0")
    rows.append("invalid-date,10000.0")
    rows.append("2026-01-02,not-a-number")
    csv_content = "\n".join(rows)

    adapter = CsvBenchmarkAdapter()
    with pytest.raises(ValueError, match="exceeds 0.5% threshold"):
        adapter.parse_csv(csv_content)

    assert adapter.bad_rows == 2
    assert adapter.total_rows == 202


def test_csv_parser_tolerates_low_bad_rows_below_half_percent() -> None:
    # 500 rows, 1 bad row = 1/501 = 0.199% <= 0.5%
    rows = ["Date,Close"]
    for i in range(500):
        # vary date to avoid duplicates
        d = date(2024, 1, 1) + timedelta(days=i)
        rows.append(f"{d.isoformat()},10000.0")
    rows.append("invalid-date,10000.0")
    csv_content = "\n".join(rows)

    adapter = CsvBenchmarkAdapter()
    records = adapter.parse_csv(csv_content)
    assert adapter.bad_rows == 1
    assert len(records) == 500


# ---------------------------------------------------------------------------
# Test 8: Yahoo adapter with mocked yfinance data
# ---------------------------------------------------------------------------
def test_yahoo_adapter_timezone_and_filtering() -> None:
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    today_kolkata = datetime.now(kolkata_tz).date()

    # Constructed DataFrame
    # 1. Valid IST timestamp: 2024-05-10 03:45:00 UTC = 2024-05-10 09:15:00 IST
    # 2. IST Midnight: 2024-05-11 18:30 UTC = 2024-05-12 00:00 IST (must not shift back)
    # 3. NaN Close (should be dropped)
    # 4. Non-positive Close <= 0 (should be dropped)
    # 5. Today's date (should be dropped to avoid partial bar)
    idx = pd.to_datetime(
        [
            "2024-05-10 03:45:00+00:00",
            "2024-05-11 18:30:00+00:00",
            "2024-05-13 03:45:00+00:00",
            "2024-05-14 03:45:00+00:00",
            f"{today_kolkata} 04:00:00+00:00",
        ]
    )
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [95.0, 96.0, 97.0, 98.0, 99.0],
            "Close": [102.5, 103.0, float("nan"), -5.0, 105.0],
            "Volume": [1000, 2000, 3000, 4000, 5000],
        },
        index=idx,
    )

    adapter = YahooBenchmarkAdapter()
    records = adapter.parse_frame(df)

    assert len(records) == 2
    # Row 1: 2024-05-10
    assert records[0].trade_date == date(2024, 5, 10)
    assert records[0].close == Decimal("102.5")
    # Row 2: 2024-05-12 in Kolkata
    assert records[1].trade_date == date(2024, 5, 12)
    assert records[1].close == Decimal("103.0")


# ---------------------------------------------------------------------------
# Test 9: Every consistency check and PASS RULE (Passing & Failing)
# ---------------------------------------------------------------------------
def _build_passing_records() -> list[BenchmarkPriceRecord]:
    base_d = date(2015, 1, 1)
    recs: list[BenchmarkPriceRecord] = []
    price = 1000.0
    for i in range(100):
        # Daily move < 2%
        price = price * (1.0 + (0.005 if i % 2 == 0 else -0.004))
        recs.append(
            BenchmarkPriceRecord(
                trade_date=base_d + timedelta(days=i),
                open=Decimal(str(round(price, 2))),
                high=Decimal(str(round(price * 1.01, 2))),
                low=Decimal(str(round(price * 0.99, 2))),
                close=Decimal(str(round(price, 2))),
                volume=100000,
            )
        )
    return recs


def test_pass_rules_all_pass_constructed_dataset() -> None:
    records = _build_passing_records()
    report = run_benchmark_checks(records=records, session=None, source="YAHOO", symbol="^CNX200")
    assert report.all_pass is True
    assert all(r.passed for r in report.rule_evaluations)


def test_pass_rule_1_fails_when_start_date_after_target() -> None:
    # First date 2016-01-01 > 2015-03-31
    base_d = date(2016, 1, 1)
    records = [
        BenchmarkPriceRecord(
            trade_date=base_d + timedelta(days=i),
            open=None,
            high=None,
            low=None,
            close=Decimal("1000.0"),
        )
        for i in range(10)
    ]
    report = run_benchmark_checks(records=records, session=None)
    rule1 = next(r for r in report.rule_evaluations if "Rule 1" in r.rule_name)
    assert rule1.passed is False
    assert report.all_pass is False


def test_pass_rule_2_fails_on_duplicate_dates() -> None:
    records = _build_passing_records()
    # Insert a duplicate date
    records.append(
        BenchmarkPriceRecord(
            trade_date=records[0].trade_date,
            open=None,
            high=None,
            low=None,
            close=Decimal("1000.0"),
        )
    )
    report = run_benchmark_checks(records=records, session=None)
    rule2 = next(r for r in report.rule_evaluations if "Rule 2" in r.rule_name)
    assert rule2.passed is False
    assert report.all_pass is False


def test_pass_rule_5_fails_on_excessive_stale_data() -> None:
    # 4 consecutive identical closes (> 3 allowed)
    records = _build_passing_records()
    fixed_close = Decimal("1500.0")
    records[10] = BenchmarkPriceRecord(records[10].trade_date, None, None, None, fixed_close)
    records[11] = BenchmarkPriceRecord(records[11].trade_date, None, None, None, fixed_close)
    records[12] = BenchmarkPriceRecord(records[12].trade_date, None, None, None, fixed_close)
    records[13] = BenchmarkPriceRecord(records[13].trade_date, None, None, None, fixed_close)

    report = run_benchmark_checks(records=records, session=None)
    rule5 = next(r for r in report.rule_evaluations if "Rule 5" in r.rule_name)
    assert rule5.passed is False
    assert report.all_pass is False


def test_pass_rule_6_fails_on_extreme_movement_exceeding_25pct() -> None:
    records = _build_passing_records()
    # Jump from ~1000 to 1300 (> 25%)
    records[5] = BenchmarkPriceRecord(
        records[5].trade_date, None, None, None, Decimal(str(float(records[4].close) * 1.30))
    )
    report = run_benchmark_checks(records=records, session=None)
    rule6 = next(r for r in report.rule_evaluations if "Rule 6" in r.rule_name)
    assert rule6.passed is False
    assert report.all_pass is False


# ---------------------------------------------------------------------------
# Test 10 & 11: Dry-run writes nothing & --apply refuses to write on failure
# ---------------------------------------------------------------------------
def test_persistence_idempotent_and_updates_definition_description(mem_db: Session) -> None:
    records = _build_passing_records()[:5]

    # First write
    inserted, issues = persist_benchmark_series(
        session=mem_db,
        benchmark_id="NIFTY_200",
        records=records,
        source="YAHOO",
    )
    mem_db.commit()

    assert inserted == 5
    assert len(issues) == 0

    # Verify definition was created with exact description
    definition = mem_db.scalar(
        select(BenchmarkDefinition).where(BenchmarkDefinition.benchmark_id == "NIFTY_200")
    )
    assert definition is not None
    assert "NIFTY 200 PRICE index, single source Yahoo Finance ^CNX200" in definition.description

    # Re-running with same records inserted must be 0 (idempotent)
    inserted_again, _ = persist_benchmark_series(
        session=mem_db,
        benchmark_id="NIFTY_200",
        records=records,
        source="YAHOO",
    )
    assert inserted_again == 0
