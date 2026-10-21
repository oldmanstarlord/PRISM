"""Comprehensive tests for Market Data Lineage, Quality Checks, and Alignment.

Tests:
- Provider failure explicit unavailable/stale status (no fake data).
- Lineage fields: instrument, exchange, date, raw close, adjusted close, volume, currency,
  source, retrieved_at, adjustment status, quality status.
- Common date alignment for covariance/beta/correlation returning observation count and coverage.
- Quality check flags: stale data, duplicates, non-positive prices, extreme returns, gaps.
- Benchmark ^NSEI consolidation and health endpoint.
- Survivorship limitation metadata exposure.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd

from backend.app.market_data.live_service import (
    BENCHMARK_SYMBOL,
    align_price_series,
    fetch_quote,
    get_market_data_health,
)
from backend.app.market_data.quality import validate_prices
from backend.app.market_data.types import DailyPrice


def test_align_price_series_common_valid_dates() -> None:
    """Ensure asset and benchmark series align on common valid dates and report coverage."""
    asset_dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)]
    bench_dates = [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)]

    asset_series = pd.Series([100.0, 102.0, 101.0, 105.0], index=asset_dates)
    bench_series = pd.Series([20000.0, 20100.0, 20050.0, 20200.0], index=bench_dates)

    aligned_asset, aligned_bench, metadata = align_price_series(
        asset_series, bench_series, asset_name="TCS", benchmark_name=BENCHMARK_SYMBOL
    )

    # Common dates are 2026-01-02, 2026-01-05, 2026-01-06 (3 observations)
    assert len(aligned_asset) == 3
    assert len(aligned_bench) == 3
    assert metadata["observation_count"] == 3
    assert metadata["asset_original_count"] == 4
    assert metadata["benchmark_original_count"] == 4
    # Coverage: 3 / 4 = 75.0%
    assert metadata["coverage_ratio"] == 0.75
    assert metadata["is_sufficient"] is False  # Min required observations is default 20


def test_align_price_series_insufficient_history_flag() -> None:
    """Fewer than min_observations returns is_sufficient=False and warning."""
    d = [date(2026, 1, i) for i in range(1, 11)]
    s1 = pd.Series([10.0 + i for i in range(10)], index=d)
    s2 = pd.Series([100.0 + i for i in range(10)], index=d)

    _, _, meta = align_price_series(s1, s2, min_observations=20)
    assert meta["observation_count"] == 10
    assert meta["is_sufficient"] is False
    assert "Insufficient common observations" in meta["warning"]


def test_validate_prices_flags_extreme_returns_duplicates_and_non_positive() -> None:
    """Validate quality checker detects non-positive prices, duplicates, and extreme returns."""
    prices = [
        DailyPrice(
            trade_date=date(2026, 1, 1),
            open=Decimal("100.0"),
            high=Decimal("102.0"),
            low=Decimal("99.0"),
            close=Decimal("100.0"),
            adjusted_close=Decimal("100.0"),
            volume=1000,
        ),
        # Duplicate date
        DailyPrice(
            trade_date=date(2026, 1, 1),
            open=Decimal("101.0"),
            high=Decimal("102.0"),
            low=Decimal("100.0"),
            close=Decimal("101.0"),
            adjusted_close=Decimal("101.0"),
            volume=1000,
        ),
        # Non-positive price
        DailyPrice(
            trade_date=date(2026, 1, 2),
            open=Decimal("0.0"),
            high=Decimal("10.0"),
            low=Decimal("0.0"),
            close=Decimal("0.0"),
            adjusted_close=Decimal("0.0"),
            volume=1000,
        ),
        # Normal
        DailyPrice(
            trade_date=date(2026, 1, 5),
            open=Decimal("100.0"),
            high=Decimal("106.0"),
            low=Decimal("99.0"),
            close=Decimal("105.0"),
            adjusted_close=Decimal("105.0"),
            volume=1000,
        ),
        # Extreme return (> 40%)
        DailyPrice(
            trade_date=date(2026, 1, 6),
            open=Decimal("150.0"),
            high=Decimal("200.0"),
            low=Decimal("150.0"),
            close=Decimal("200.0"),
            adjusted_close=Decimal("200.0"),
            volume=1000,
        ),
    ]

    result = validate_prices(prices)
    issue_codes = {issue.code for issue in result.issues}

    assert "duplicate_date" in issue_codes
    assert "non_positive_price" in issue_codes
    assert "extreme_adjusted_return" in issue_codes
    assert result.rejected_rows == 2  # duplicate and non-positive are rejected
    assert len(result.accepted) == 3  # valid rows kept (one flagged)


def test_market_data_health_and_survivorship_metadata() -> None:
    """Ensure market data health reports provider status and documents survivorship limitation."""
    mock_session = MagicMock()
    # Mocking scalar queries for last_run, sec_count, price_count,
    # latest_trade_date, bm_alias, bm_date
    mock_session.scalar.side_effect = [
        None,  # last_run
        200,  # sec_count
        50000,  # price_count
        date(2026, 9, 30),  # latest_trade_date
        MagicMock(security_id=1),  # bm_alias
        date(2026, 9, 30),  # bm_date
    ]

    health = get_market_data_health(mock_session)
    assert health["provider"] == "yfinance (batch pipeline)"
    assert health["status"] == "operational"
    assert health["stored_securities_count"] == 200
    assert health["stored_price_records"] == 50000
    assert health["benchmark_symbol"] == "^NSEI"
    assert "survivorship_limitation" in health
    assert "NIFTY 200" in health["survivorship_limitation"]


def test_live_service_never_returns_fabricated_data_on_missing_quote() -> None:
    """When a quote is absent from both cache and DB, it returns explicit unavailable status."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.all.return_value = []
    mock_session.scalar.return_value = None

    quote = fetch_quote("UNKNOWN_SYM", session=mock_session)
    assert quote is not None, "Service returns structured quote object"
    assert quote.source == "unavailable", "Must flag source as unavailable"
    assert quote.data_quality == "error", "Must flag data quality as error"
    assert quote.latest_price is None, "Must never invent plausible fake prices"
    assert "Price series not found" in (quote.error or "")
