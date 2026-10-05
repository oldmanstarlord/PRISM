"""Tests for benchmark adapter, validation rules, and series persistence (FR-D8, FR-D9)."""

from datetime import date
from decimal import Decimal

from backend.app.market_data.benchmark import (
    BenchmarkPriceRecord,
    CsvBenchmarkAdapter,
    validate_benchmark_records,
)

SAMPLE_CSV = """Date,Open,High,Low,Close,Volume
2026-09-28,12560.0,12620.0,12540.0,12610.0,165000000
2026-09-29,12620.0,12650.0,12570.0,12590.0,140000000
2026-09-30,12600.0,12640.0,12580.0,12630.0,175000000
"""


def test_csv_benchmark_adapter_parses_records() -> None:
    adapter = CsvBenchmarkAdapter()
    records = adapter.parse_csv(SAMPLE_CSV)

    assert len(records) == 3
    assert records[0].trade_date == date(2026, 9, 28)
    assert records[0].close == Decimal("12610.0")
    assert records[0].volume == 165000000
    assert records[2].trade_date == date(2026, 9, 30)
    assert records[2].close == Decimal("12630.0")


def test_validate_benchmark_rejects_duplicate_date() -> None:
    records = [
        BenchmarkPriceRecord(
            date(2026, 9, 28), Decimal("100"), Decimal("105"), Decimal("95"), Decimal("102")
        ),
        BenchmarkPriceRecord(
            date(2026, 9, 28), Decimal("100"), Decimal("105"), Decimal("95"), Decimal("103")
        ),
    ]
    accepted, issues = validate_benchmark_records(records)
    assert len(accepted) == 1
    assert any("duplicate_date" in issue for issue in issues)


def test_validate_benchmark_flags_extreme_return() -> None:
    records = [
        BenchmarkPriceRecord(
            date(2026, 9, 28), Decimal("100"), Decimal("105"), Decimal("95"), Decimal("100")
        ),
        # Move from 100 to 125 is 25% (> 15% index threshold)
        BenchmarkPriceRecord(
            date(2026, 9, 29), Decimal("120"), Decimal("126"), Decimal("118"), Decimal("125")
        ),
    ]
    accepted, issues = validate_benchmark_records(records)
    assert len(accepted) == 2
    assert any("extreme_index_return" in issue for issue in issues)


def test_validate_benchmark_rejects_high_less_than_low() -> None:
    records = [
        BenchmarkPriceRecord(
            date(2026, 9, 28), Decimal("100"), Decimal("90"), Decimal("110"), Decimal("100")
        ),
    ]
    accepted, issues = validate_benchmark_records(records)
    assert len(accepted) == 0
    assert any("high_less_than_low" in issue for issue in issues)
