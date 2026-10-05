"""Test API endpoints for Step 11 news, policy events, and rules (Step 11, D1, D3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_policy_rules_endpoint(client: TestClient):
    """GET /api/v1/policy/rules returns list of policy rules with version, reviewer, rationale."""
    response = client.get("/api/v1/policy/rules")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 10

    first = data[0]
    assert "rule_key" in first
    assert "version" in first
    assert "reviewer" in first
    assert "rationale" in first
    assert "direction" in first
    assert "severity" in first


def test_get_recent_policy_events_endpoint(client: TestClient):
    """GET /api/v1/policy/events/recent returns recent policy events with disclaimer."""
    response = client.get("/api/v1/policy/events/recent?limit=5")
    assert response.status_code == 200

    data = response.json()
    assert "events" in data
    assert "total_count" in data
    assert "disclaimer" in data
    assert "Markets may have already priced this in" in data["disclaimer"]


def test_get_stock_news_endpoint(client: TestClient):
    """GET /api/v1/stocks/{symbol}/news returns news and matched policy events for stock."""
    response = client.get("/api/v1/stocks/HDFCBANK/news")
    assert response.status_code == 200

    data = response.json()
    assert data["symbol"] == "HDFCBANK"
    assert "company_name" in data
    assert "items" in data
    assert "disclaimer" in data
    assert "Markets may have already priced this in" in data["disclaimer"]


def test_put_policy_rule_requires_rationale_and_reviewer(client: TestClient):
    """PUT /api/v1/policy/rules/{key} fails validation without required rationale and reviewer."""
    # Missing rationale & reviewer
    response = client.put(
        "/api/v1/policy/rules/POL_RBI_RATE_HIKE_V1",
        json={"severity": 8.0},
    )
    assert response.status_code == 422  # Pydantic validation error


def test_put_policy_rule_creates_new_version(client: TestClient):
    """PUT /api/v1/policy/rules/{key} creates an updated version row with audit trail."""
    payload = {
        "rationale": "Updated economic rationale for rate hike sensitivity testing.",
        "reviewer": "Chief Risk Officer",
        "severity": 7.8,
        "active": True,
    }
    response = client.put(
        "/api/v1/policy/rules/POL_RBI_RATE_HIKE_V1",
        json=payload,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["rule_key"] == "POL_RBI_RATE_HIKE_V1"
    assert data["reviewer"] == "Chief Risk Officer"
    assert data["severity"] == 7.8
    assert data["active"] is True
    assert data["version"] != "1.0.0"
