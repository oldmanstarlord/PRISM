"""API coverage for Step 13 persisted validation evidence."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.validation.schemas import (
    ValidationResultOut,
    ValidationRunDetailOut,
    ValidationRunSummaryOut,
)


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_session] = lambda: MagicMock()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


def test_validation_run_list_and_detail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = uuid4()
    summary = ValidationRunSummaryOut(
        id=run_id,
        kind="historical_score_validation",
        config_fingerprint="a" * 64,
        period="2024-01-01:2025-12-31",
        started_at=datetime(2026, 10, 6, tzinfo=UTC),
        completed_at=datetime(2026, 10, 6, 0, 1, tzinfo=UTC),
        status="failed",
        notes={"failures": ["Score did not beat beta."]},
    )
    detail = ValidationRunDetailOut(
        **summary.model_dump(),
        results=[
            ValidationResultOut(
                metric_key="beats_baseline:forward_max_drawdown_20d",
                component_key="beta",
                value=0.0,
                baseline_value=0.2,
                n=8,
                period="all",
            )
        ],
    )
    monkeypatch.setattr(
        "backend.app.api.v1.router.list_validation_runs", lambda _session: [summary]
    )
    monkeypatch.setattr(
        "backend.app.api.v1.router.get_validation_run", lambda _session, _run_id: detail
    )

    listed = client.get("/api/v1/validation/runs")
    fetched = client.get(f"/api/v1/validation/runs/{run_id}")

    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "failed"
    assert fetched.status_code == 200
    assert fetched.json()["results"][0]["value"] == 0.0


def test_validation_run_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(_session: object, _run_id: object) -> None:
        raise KeyError("missing")

    monkeypatch.setattr("backend.app.api.v1.router.get_validation_run", missing)
    response = client.get(f"/api/v1/validation/runs/{uuid4()}")
    assert response.status_code == 404
