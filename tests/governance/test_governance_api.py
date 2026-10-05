"""API tests for GET /stocks/{symbol}/governance endpoint."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import get_session
from backend.app.main import app


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def client(mock_session):
    app.dependency_overrides[get_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_get_stock_governance_not_found(client: TestClient) -> None:
    """Non-existent stock returns 404."""
    with patch("backend.app.governance.service.get_governance_signals", return_value=None):
        resp = client.get("/api/v1/stocks/UNKNOWN/governance")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


def test_get_stock_governance_success(client: TestClient) -> None:
    """Existing stock returns full point-in-time governance response envelope."""
    mock_data = {
        "symbol": "INFY",
        "security_id": str(uuid4()),
        "as_of": "2026-01-15",
        "pledge": {
            "quarter_end": "2025-12-31",
            "pledge_level_pct": 0.0,
            "pledge_change_pct": 0.0,
            "n_quarters_available": 4,
            "status": "ok",
            "limitations": [],
        },
        "promoter_holding": {
            "promoter_pct": 14.8,
            "promoter_change_pct": 0.0,
            "status": "ok",
        },
        "institutional_flow": {
            "quarter_end": "2025-12-31",
            "fii_pct": 34.2,
            "dii_pct": 35.1,
            "combined_pct": 69.3,
            "institutional_change_pct": 0.5,
            "n_quarters_available": 4,
            "status": "ok",
            "limitations": [],
        },
        "insider_activity": {
            "window_days": 180,
            "window_start": "2025-07-19",
            "window_end": "2026-01-15",
            "buy_value_inr": 1000000.0,
            "sell_value_inr": 2000000.0,
            "net_sell_value_inr": 1000000.0,
            "trade_count": 2,
            "insider_sell_ratio": 0.00001,
            "status": "ok",
            "limitations": [],
        },
        "holding_table": [
            {
                "quarter_end": "2025-12-31",
                "promoter_pct": 14.8,
                "promoter_pledged_pct_of_promoter": 0.0,
                "fii_pct": 34.2,
                "dii_pct": 35.1,
                "public_pct": 15.9,
                "published_at": "2026-01-10T10:00:00Z",
                "source": "CSV_IMPORT",
            }
        ],
        "recent_insider_trades": [
            {
                "person_category": "Director",
                "txn_type": "sell",
                "quantity": 1000,
                "value_inr": 1800000.0,
                "txn_date": "2025-11-20",
                "published_at": "2025-11-22T08:00:00Z",
                "source": "CSV_IMPORT",
            }
        ],
        "limitations": [
            "Governance signals are descriptive and do not predict future price movements."
        ],
        "method_version": "governance_analysis_v1",
        "config_key": "governance_analysis",
    }

    with patch("backend.app.governance.service.get_governance_signals", return_value=mock_data):
        resp = client.get("/api/v1/stocks/INFY/governance")
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "INFY"
        assert body["pledge"]["pledge_level_pct"] == 0.0
        assert body["promoter_holding"]["promoter_pct"] == 14.8
        assert body["institutional_flow"]["combined_pct"] == 69.3
        assert len(body["holding_table"]) == 1
        assert len(body["recent_insider_trades"]) == 1
        assert body["method_version"] == "governance_analysis_v1"
