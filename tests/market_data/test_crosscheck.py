"""Tests for price cross-check comparisons, mismatch rate calculation,
and no auto-correction (NFR-9).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.db.models import PriceDailyRaw
from backend.app.market_data.crosscheck import run_price_crosscheck


def test_crosscheck_compares_and_flags_mismatches() -> None:
    sec_id = uuid4()
    t_date = date(2026, 10, 1)

    # 1. Price record: yfinance close = 100.00
    price_rec = PriceDailyRaw(
        security_id=sec_id,
        trade_date=t_date,
        open=Decimal("99.00"),
        high=Decimal("101.00"),
        low=Decimal("98.50"),
        close=Decimal("100.00"),
        volume=100000,
        currency="INR",
        source="yfinance",
    )

    # 2. Official exchange close = 101.00 -> rel_diff = |100 - 101| / 101 = 1 / 101 ~ 0.0099 (0.99%)
    official_data = {
        ("TESTSYM", t_date): Decimal("101.00"),
    }

    mock_session = MagicMock()
    mock_session.execute.return_value.all.return_value = [("TESTSYM", sec_id)]
    mock_session.scalars.return_value.all.return_value = [price_rec]
    mock_session.scalar.return_value = None  # no existing DataCrosscheck

    # Tolerance 0.5% (0.005) -> Should be MISMATCH
    summary = run_price_crosscheck(
        session=mock_session,
        official_data=official_data,
        sample_dates=[t_date],
        tolerance=Decimal("0.005"),
    )

    assert summary.total_checked == 1
    assert summary.mismatches == 1
    assert summary.matches == 0
    assert summary.mismatch_rate == 1.0
    assert len(summary.worst_offenders) == 1
    assert summary.worst_offenders[0]["symbol"] == "TESTSYM"
    assert round(summary.worst_offenders[0]["rel_diff"], 4) == 0.0099

    # Verify that the price_rec itself was NOT changed (no auto-correction)
    assert price_rec.close == Decimal("100.00")

    # If tolerance is 2% (0.02) -> Should be MATCH
    summary_wide = run_price_crosscheck(
        session=mock_session,
        official_data=official_data,
        sample_dates=[t_date],
        tolerance=Decimal("0.020"),
    )
    assert summary_wide.total_checked == 1
    assert summary_wide.matches == 1
    assert summary_wide.mismatches == 0
    assert summary_wide.mismatch_rate == 0.0
