"""Step 14 API contracts for operations, alerts, watchlists, and limitations."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.operations.schemas import AlertOut, WatchlistOut


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_session] = lambda: MagicMock()
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.pop(get_session, None)


def test_alerts_endpoint_keeps_explanation(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    item = AlertOut(
        id=uuid4(), created_at=datetime.now(UTC), subject_type="stock", subject_id="s1",
        alert_type="risk_jump", reason="Risk rose 11 points.", inputs_ref={"threshold": 10},
        score=11, status="open", config_version="1.0.0", config_fingerprint="f" * 64,
    )
    monkeypatch.setattr("backend.app.api.v1.router.list_alerts", lambda _session, _limit: [item])
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json()[0]["reason"] == "Risk rose 11 points."
    assert response.json()[0]["inputs_ref"]["threshold"] == 10


def test_watchlist_create_and_delete(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    watchlist_id = uuid4()
    output = WatchlistOut(
        id=watchlist_id, name="Banks", created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC), items=[],
    )
    monkeypatch.setattr(
        "backend.app.api.v1.router.create_watchlist", lambda _session, _payload: output
    )
    monkeypatch.setattr("backend.app.api.v1.router.delete_watchlist", lambda _session, _id: True)
    created = client.post("/api/v1/watchlists", json={"name": "Banks", "items": []})
    deleted = client.delete(f"/api/v1/watchlists/{watchlist_id}")
    assert created.status_code == 201 and created.json()["name"] == "Banks"
    assert deleted.status_code == 204
