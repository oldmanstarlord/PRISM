"""Integration tests for macroeconomic API endpoints (Step 9)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_macro_regime_latest(client: TestClient) -> None:
    """GET /api/v1/macro/regime/latest returns valid regime and features."""
    response = client.get("/api/v1/macro/regime/latest")
    assert response.status_code == 200
    data = response.json()
    assert "regime" in data
    assert data["regime"] in ("calm", "trending", "stressed")
    assert "features" in data
    assert "as_of" in data
    assert "config_version" in data


def test_get_macro_regime_root_alias(client: TestClient) -> None:
    """GET /macro/regime/latest also works without /api/v1 prefix."""
    response = client.get("/macro/regime/latest")
    assert response.status_code == 200
    data = response.json()
    assert "regime" in data


def test_get_macro_series_list(client: TestClient) -> None:
    """GET /api/v1/macro/series returns list of active series definitions."""
    response = client.get("/api/v1/macro/series")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    keys = [item["series_key"] for item in data]
    assert "crude_oil" in keys
    assert "usd_inr" in keys
    assert "in_10y_yield" in keys
    assert "india_vix" in keys
    assert "fii_dii_net_flows" in keys


def test_get_macro_series_detail(client: TestClient) -> None:
    """GET /api/v1/macro/series/crude_oil returns series metadata and observations."""
    response = client.get("/api/v1/macro/series/crude_oil?limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["series"]["series_key"] == "crude_oil"
    assert "observations" in data
    assert isinstance(data["observations"], list)


def test_get_macro_series_detail_not_found(client: TestClient) -> None:
    """GET for unknown macro series returns 404."""
    response = client.get("/api/v1/macro/series/unknown_crypto_coin")
    assert response.status_code == 404


def test_get_industry_macro_sensitivity(client: TestClient) -> None:
    """GET /api/v1/industries/{industry}/macro-sensitivity returns sensitivities."""
    response = client.get("/api/v1/industries/Automobile/macro-sensitivity")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "beta" in item
        assert "t_stat" in item
        assert "is_significant" in item
