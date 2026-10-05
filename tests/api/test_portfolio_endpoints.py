"""Tests for Step 3 portfolio API endpoints."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base
from backend.app.db.models import Security, SecurityAlias
from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.portfolio.schemas import PortfolioRiskScoreOut


@pytest.fixture
def mock_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        sec = Security(
            id=uuid4(),
            isin="INE009A01021",
            company_name="Infosys Ltd",
        )
        session.add(sec)
        session.flush()

        alias = SecurityAlias(
            security_id=sec.id,
            symbol="INFY",
            exchange="NSE",
            valid_from=date(2020, 1, 1),
            source="NSE",
            ingested_at=date(2020, 1, 1),
        )
        session.add(alias)
        session.commit()
        yield session


def test_create_and_get_portfolio_endpoints(mock_db: Session) -> None:
    app.dependency_overrides[get_session] = lambda: mock_db
    client = TestClient(app)
    try:
        # Create portfolio
        payload = {
            "name": "API Test Portfolio",
            "description": "Created via REST API",
            "holdings": [{"symbol": "INFY", "weight": 0.8}],
        }
        res = client.post("/api/v1/portfolios", json=payload)
        assert res.status_code == 200
        data = res.json()
        port_id = data["id"]
        assert data["name"] == "API Test Portfolio"
        # 0.8 INFY + 0.2 CASH
        assert len(data["holdings"]) == 2

        # List portfolios
        list_res = client.get("/api/v1/portfolios")
        assert list_res.status_code == 200
        ports = list_res.json()
        assert len(ports) >= 1

        # Get portfolio by ID
        get_res = client.get(f"/api/v1/portfolios/{port_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == port_id
    finally:
        app.dependency_overrides.clear()


def test_import_portfolio_csv_endpoint(mock_db: Session) -> None:
    app.dependency_overrides[get_session] = lambda: mock_db
    client = TestClient(app)
    try:
        # Valid CSV upload via multipart
        csv_data = "symbol,weight\nINFY,1.0\n"
        res = client.post(
            "/api/v1/portfolios/import-csv",
            data={"name": "CSV Port"},
            files={"file": ("holdings.csv", csv_data, "text/csv")},
        )
        assert res.status_code == 200
        result = res.json()
        assert result["portfolio"] is not None
        assert not result["errors"]

        # CSV with errors
        bad_csv = "symbol,weight\nBAD_SYMBOL,0.5\n"
        res_bad = client.post(
            "/api/v1/portfolios/import-csv",
            data={"name": "Bad CSV Port"},
            files={"file": ("bad.csv", bad_csv, "text/csv")},
        )
        assert res_bad.status_code == 200
        result_bad = res_bad.json()
        assert result_bad["portfolio"] is None
        assert len(result_bad["errors"]) > 0
        assert result_bad["errors"][0]["symbol"] == "BAD_SYMBOL"
    finally:
        app.dependency_overrides.clear()


def test_latest_portfolio_risk_score_endpoint(
    mock_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio_id = uuid4()
    score_run_id = uuid4()
    monkeypatch.setattr(
        "backend.app.api.v1.router.portfolio_service.get_latest_portfolio_risk_score",
        lambda session, requested_id: PortfolioRiskScoreOut(
            portfolio_id=requested_id,
            as_of=date(2026, 10, 6),
            stock_score_run_id=score_run_id,
            total_score=54.3,
            holding_risk_score=56.0,
            structure_score=47.5,
            structure_components={
                "cluster_concentration": 70.0,
                "effective_bets": 25.0,
            },
            confidence=40.0,
            weighted_holding_confidence=70.0,
            weakest_large_holding_confidence=40.0,
            coverage=1.0,
            status="ok",
            method_version="portfolio-risk-score-v2-draft",
            config_version="2.0.0",
            computed_at=datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
        ),
    )
    app.dependency_overrides[get_session] = lambda: mock_db
    try:
        response = TestClient(app).get(
            f"/api/v1/portfolios/{portfolio_id}/risk-score/latest"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["holding_risk_score"] == 56.0
        assert data["structure_components"]["effective_bets"] == 25.0
        assert data["confidence"] == 40.0
    finally:
        app.dependency_overrides.clear()
