"""Tests for Step 5 Stock endpoints: latest scores, envelope detail, and history."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import (
    ConfidenceFactorValue,
    ScoreComponentDefinition,
    ScoreComponentValue,
    ScoreRun,
    Security,
    StockRiskResult,
)
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


def test_get_stock_scores_latest_empty(client: TestClient, mock_session: MagicMock) -> None:
    mock_session.scalars.return_value.first.return_value = None

    response = client.get("/api/v1/stocks/scores/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 0
    assert data["items"] == []


def test_get_stock_scores_latest_with_data(client: TestClient, mock_session: MagicMock) -> None:
    run_id = uuid4()
    mock_run = ScoreRun(
        id=run_id,
        as_of_date=date(2026, 1, 15),
        data_cutoff=datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC),
        model_config_id=uuid4(),
        config_version="1.0.0",
        config_fingerprint="cfg_fp",
        input_fingerprint="inp_fp",
        status="completed",
        total_securities=1,
        scored_securities=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    mock_session.scalars.return_value.first.return_value = mock_run

    sec_id = uuid4()
    mock_res = StockRiskResult(
        id=uuid4(),
        run_id=run_id,
        security_id=sec_id,
        symbol="TCS",
        total_score=Decimal("42.5"),
        confidence=Decimal("88.0"),
        data_coverage=Decimal("0.85"),
        dimension_scores={"market": {"score": 42.5, "weight": 25.0, "status": "ok"}},
        top_reasons=[
            {
                "component_id": "ewma_volatility",
                "dimension": "market",
                "name": "EWMA Volatility",
                "contribution": 10.6,
                "text": "EWMA Volatility contributes +10.6 pts",
            }
        ],
        limitations=[],
        computed_at=datetime.now(UTC),
    )

    mock_session.scalar.return_value = 1
    mock_session.execute.return_value.all.return_value = [
        (mock_res, "Information Technology", "Tata Consultancy Services Ltd.")
    ]

    response = client.get("/api/v1/stocks/scores/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["symbol"] == "TCS"
    assert data["items"][0]["total_score"] == 42.5
    assert data["items"][0]["confidence"] == 88.0


def test_get_stock_risk_latest_envelope(client: TestClient, mock_session: MagicMock) -> None:
    sec_id = uuid4()
    run_id = uuid4()
    mock_sec = Security(
        id=sec_id,
        isin="INE009A01021",
        company_name="Infosys Ltd.",
        industry="Information Technology",
        is_active=True,
    )
    mock_run = ScoreRun(
        id=run_id,
        as_of_date=date(2026, 1, 15),
        data_cutoff=datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC),
        model_config_id=uuid4(),
        config_version="1.0.0",
        config_fingerprint="cfg_fp",
        input_fingerprint="inp_fp",
        status="completed",
        total_securities=1,
        scored_securities=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    mock_res = StockRiskResult(
        id=uuid4(),
        run_id=run_id,
        security_id=sec_id,
        symbol="INFY",
        total_score=Decimal("55.0"),
        confidence=Decimal("80.0"),
        data_coverage=Decimal("0.75"),
        dimension_scores={"market": {"score": 55.0, "weight": 25.0, "status": "ok"}},
        top_reasons=[],
        limitations=[],
        computed_at=datetime.now(UTC),
    )

    # Mock DB query sequence
    def mock_scalars(statement):
        result = MagicMock()
        stmt_str = str(statement).lower()
        if "from security" in stmt_str:
            result.first.return_value = mock_sec
        elif "from stock_risk_result" in stmt_str:
            result.first.return_value = mock_res
        elif "from score_component_definition" in stmt_str:
            result.all.return_value = [
                ScoreComponentDefinition(
                    id=uuid4(),
                    component_id="ewma_volatility",
                    dimension="market",
                    name="EWMA Volatility",
                    description="",
                    direction="higher_is_riskier",
                    scope="universe",
                    min_group_size=5,
                    weight=Decimal("1.0"),
                    active=True,
                    introduced_in_step="Step 5",
                )
            ]
        elif "from score_component_value" in stmt_str:
            result.all.return_value = [
                ScoreComponentValue(
                    id=uuid4(),
                    run_id=run_id,
                    security_id=sec_id,
                    component_id="ewma_volatility",
                    raw_value=Decimal("0.24"),
                    percentile_rank=Decimal("55.0"),
                    points=Decimal("55.0"),
                    status="ok",
                    data_as_of=date(2026, 1, 15),
                    data_age_days=0,
                    evidence_ref={"observations": 250},
                )
            ]
        elif "from confidence_factor_value" in stmt_str:
            result.all.return_value = [
                ConfidenceFactorValue(
                    id=uuid4(),
                    run_id=run_id,
                    security_id=sec_id,
                    factor_name="data_coverage",
                    factor_value=Decimal("0.75"),
                    weight=Decimal("1.0"),
                    cap_applied=None,
                )
            ]
        else:
            result.first.return_value = None
            result.all.return_value = []
        return result

    mock_session.scalars.side_effect = mock_scalars

    def mock_get(entity, ident):
        if entity is Security or entity == Security:
            return mock_sec
        if entity is ScoreRun or entity == ScoreRun:
            return mock_run
        return None

    mock_session.get.side_effect = mock_get

    response = client.get("/api/v1/stocks/INFY/risk/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == "stock:INFY"
    assert data["symbol"] == "INFY"
    assert data["total_score"] == 55.0
    assert data["confidence"]["score"] == 80.0
    assert len(data["components"]) == 1
    assert data["components"][0]["component_id"] == "ewma_volatility"
    assert data["components"][0]["raw_value"] == 0.24


def test_get_stock_risk_latest_not_found(client: TestClient, mock_session: MagicMock) -> None:
    mock_session.scalars.return_value.first.return_value = None

    response = client.get("/api/v1/stocks/NONEXISTENT/risk/latest")
    assert response.status_code == 404
