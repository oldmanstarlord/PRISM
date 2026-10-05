"""Tests for Step 2 data endpoints:
/data/quality/summary, /data/freshness, /data/crosscheck/latest.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db.models import DataCrosscheck
from backend.app.db.session import get_session
from backend.app.main import app


def test_data_quality_summary_endpoint() -> None:
    mock_session = MagicMock()
    # Return sample counts
    mock_session.scalar.side_effect = [500000, 590000, 2500, 500000, 120]

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/data/quality/summary")
        assert res.status_code == 200
        data = res.json()
        assert "datasets" in data
        assert data["datasets"]["price_daily_raw"]["total_rows"] == 500000
        assert data["datasets"]["security_market_stat"]["thin_trading_flagged"] == 120
    finally:
        app.dependency_overrides.clear()


def test_data_freshness_endpoint() -> None:
    mock_session = MagicMock()
    today = date(2026, 10, 1)
    mock_session.scalar.side_effect = [today, today, today, today, date(2026, 6, 30)]

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/data/freshness")
        assert res.status_code == 200
        data = res.json()
        assert data["datasets"]["price_daily_raw"] == "2026-10-01"
        assert data["datasets"]["security_share_count"] == "2026-06-30"
    finally:
        app.dependency_overrides.clear()


def test_latest_crosscheck_endpoint() -> None:
    mock_session = MagicMock()
    run_id = uuid4()
    mock_session.scalar.return_value = run_id

    now = datetime.now(UTC)
    row = DataCrosscheck(
        id=uuid4(),
        run_id=run_id,
        security_id=uuid4(),
        trade_date=date(2026, 10, 1),
        source_a="yfinance",
        source_b="official_exchange",
        close_a=Decimal("100.00"),
        close_b=Decimal("100.00"),
        rel_diff=Decimal("0.0"),
        status="match",
        checked_at=now,
    )
    mock_session.scalars.return_value.all.return_value = [row]

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/data/crosscheck/latest")
        assert res.status_code == 200
        data = res.json()
        assert data["run_id"] == str(run_id)
        assert data["total_checked"] == 1
        assert data["matches"] == 1
        assert data["mismatches"] == 0
    finally:
        app.dependency_overrides.clear()
