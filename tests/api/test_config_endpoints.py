"""Tests for Step 1 API endpoints: /config/models, /config/components, and /meta."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db.models import ModelConfig
from backend.app.db.session import get_session
from backend.app.main import app


def test_meta_endpoint_returns_disclaimer_and_universe() -> None:
    mock_session = MagicMock()
    # No completed runs in DB
    mock_session.scalar.return_value = None
    mock_session.scalars.return_value.all.return_value = []

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/meta")
        assert res.status_code == 200
        data = res.json()
        assert data["platform"] == "PRISM"
        assert data["universe"] == "NIFTY 200"
        assert "NOT investment advice" in data["disclaimer"]
        assert "MST/correlation is never presented as causal" in data["disclaimer"]
        assert data["latest_pipeline_runs"]["sector_divergence"] is None
        assert data["latest_pipeline_runs"]["correlation_mst"] is None
    finally:
        app.dependency_overrides.clear()


def test_config_components_endpoint() -> None:
    mock_session = MagicMock()
    # Force DB query to fail so it falls back to in-memory registry
    mock_session.scalars.side_effect = Exception("DB table not yet created")

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/config/components")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] >= 12
        assert any(c["component_id"] == "volatility_60d" for c in data["items"])
        assert any(c["component_id"] == "sector_divergence_residual_20d" for c in data["items"])

        # Filter by dimension
        res_market = client.get("/api/v1/config/components?dimension=market")
        assert res_market.status_code == 200
        data_market = res_market.json()
        assert all(c["dimension"] == "market" for c in data_market["items"])
    finally:
        app.dependency_overrides.clear()


def test_config_models_endpoint() -> None:
    mock_session = MagicMock()
    now = datetime.now(UTC)
    mock_row = ModelConfig(
        id=uuid4(),
        config_key="risk_score_weights",
        version="v1",
        status="draft",
        configuration={"market": 25.0},
        configuration_hash="dummyhash",
        created_at=now,
        updated_at=now,
    )
    mock_session.scalars.return_value.all.return_value = [mock_row]

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        res = client.get("/api/v1/config/models")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 1
        item = data["items"][0]
        assert item["config_key"] == "risk_score_weights"
        assert item["version"] == "v1"
        assert item["status"] == "draft"
    finally:
        app.dependency_overrides.clear()
