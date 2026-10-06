"""Integration tests for corporate announcements & explainable events API endpoints (Step 10)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_stock_events_endpoint(client: TestClient) -> None:
    """GET /api/v1/stocks/{symbol}/events returns 200 with structured events and disclaimer."""
    response = client.get("/api/v1/stocks/TCS/events")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "TCS"
    assert "events" in data
    assert isinstance(data["events"], list)
    assert "disclaimer" in data
    assert "priced this in" in data["disclaimer"]

    if len(data["events"]) > 0:
        event = data["events"][0]
        assert "id" in event
        assert "event_type" in event
        assert "importance" in event
        assert 1.0 <= event["importance"] <= 10.0
        assert "importance_components" in event
        assert "effective_trading_date" in event


def test_get_recent_events_endpoint(client: TestClient) -> None:
    """GET /api/v1/events/recent returns recent announcements across stocks with filters."""
    response = client.get("/api/v1/events/recent?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "events" in data
    assert "disclaimer" in data
    assert "priced this in" in data["disclaimer"]


def test_get_recent_events_filter_by_type(client: TestClient) -> None:
    """GET /api/v1/events/recent respects event_type filter."""
    response = client.get("/api/v1/events/recent?event_type=regulatory_action")
    assert response.status_code == 200
    data = response.json()
    for ev in data["events"]:
        assert ev["event_type"] == "regulatory_action"


def test_get_stock_events_not_found(client: TestClient) -> None:
    """GET /api/v1/stocks/{symbol}/events returns 404 for unknown ticker."""
    response = client.get("/api/v1/stocks/UNKNOWN_INVALID_TICKER/events")
    assert response.status_code == 404
