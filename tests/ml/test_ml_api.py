"""API contract tests for ML risk endpoints under /api/v1/ml/."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import backend.app.ml.router as ml_router_mod
from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.session import get_session
from backend.app.main import app


@pytest.fixture(autouse=True)
def persisted_ml_outputs(monkeypatch: pytest.MonkeyPatch):
    """API handlers render persisted service results and never run model fitting."""
    model_statuses = {
        "volatility_forecast_21d": {
            "model_name": "21-Session Volatility Forecast",
            "model_version": "2.0.0",
            "model_type": "supervised volatility regression",
            "status": "baseline_selected",
            "data_cutoff": "2026-10-20",
            "metrics_vs_baseline": {"test": {"qlike": 0.12}},
        }
    }
    volatility = {
        "status": "baseline_selected",
        "portfolio_forecast": None,
        "holdings_forecasts": [
            {
                "symbol": "RELIANCE",
                "status": "baseline_selected",
                "forecast_volatility": 0.16,
                "lower_bound_90": 0.12,
                "upper_bound_90": 0.21,
            },
            {
                "symbol": "TCS",
                "status": "insufficient_data",
                "forecast_volatility": None,
                "failure_reason": "insufficient_history",
            },
        ],
        "portfolio_reason": "requires_covariance_forecast",
    }
    regime = {
        "status": "ready",
        "market_regime": {
            "active_regime_name": "Calm / Normal",
            "filtered_probability": 0.8,
        },
    }
    anomalies = {
        "status": "ready",
        "anomaly_analysis": {
            "unusual_holdings": [
                {"symbol": "RELIANCE", "status": "ready", "anomaly_score": 55.0},
                {"symbol": "TCS", "status": "insufficient_data"},
                {"symbol": "INFY", "status": "ready", "anomaly_score": 82.0},
            ]
        },
    }
    score = {
        "status": "ready",
        "score_validation": {
            "models": {
                "five_factor_fixed_weights": {
                    "volatility_21d": {"mean_monthly_spearman_ic": 0.1}
                }
            },
            "baseline_comparisons": {},
        },
    }
    monkeypatch.setattr(
        ml_router_mod._ml_service,
        "get_model_statuses",
        lambda session: model_statuses,
    )
    monkeypatch.setattr(
        ml_router_mod._ml_service,
        "get_volatility_insights",
        lambda symbols, weights, session: volatility,
    )
    monkeypatch.setattr(
        ml_router_mod._ml_service, "get_market_regime_insights", lambda session: regime
    )
    monkeypatch.setattr(
        ml_router_mod._ml_service,
        "get_anomaly_insights",
        lambda symbols, session, company_names=None: anomalies,
    )
    monkeypatch.setattr(
        ml_router_mod._ml_service,
        "get_risk_score_validation_insights",
        lambda symbols, session: score,
    )
    monkeypatch.setattr(
        ml_router_mod._ml_service,
        "get_comprehensive_ai_insights",
        lambda symbols, weights, session, company_names=None: {
            "model_statuses": model_statuses,
            "volatility": volatility,
            "regime": regime,
            "anomalies": anomalies,
            "score_validation": score,
            "governance": {
                "methodology_version": "ml-risk-v2",
                "disclaimer": "PRISM does NOT forecast price direction.",
                "is_model_estimate": True,
            },
        },
    )
    monkeypatch.setattr(
        ml_router_mod,
        "_get_company_names",
        lambda session, symbols: {symbol: symbol for symbol in symbols},
    )
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=UUID("00000000-0000-0000-0000-000000000001"), email="ml-test@prism.local"
    )
    app.dependency_overrides[get_session] = lambda: object()
    yield
    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(get_session, None)


def test_get_model_status():
    """Verify GET /api/v1/ml/status returns model registry cards and readiness."""
    client = TestClient(app)
    resp = client.get("/api/v1/ml/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert "models" in payload
    assert isinstance(payload["models"], dict)


def test_post_volatility_forecast():
    """Verify POST /api/v1/ml/volatility-forecast returns point and interval estimates."""
    client = TestClient(app)
    req = {
        "holdings": [
            {"symbol": "RELIANCE", "weight": 0.6},
            {"symbol": "TCS", "weight": 0.4},
        ]
    }
    resp = client.post("/api/v1/ml/volatility-forecast", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "baseline_selected"
    assert data["portfolio_forecast"] is None
    assert len(data["holdings_forecasts"]) == 2


def test_get_market_regime():
    """Verify GET /api/v1/ml/market-regime returns filtered probabilities."""
    client = TestClient(app)
    resp = client.get("/api/v1/ml/market-regime")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert "market_regime" in data
    regime = data["market_regime"]
    assert regime["active_regime_name"] in ["Calm / Normal", "Turbulent / Stressed"]
    assert 0.0 <= regime["filtered_probability"] <= 1.0


def test_post_anomalies():
    """Verify POST /api/v1/ml/anomalies returns ranked outlier diagnostics."""
    client = TestClient(app)
    req = {"symbols": ["RELIANCE", "TCS", "INFY"]}
    resp = client.post("/api/v1/ml/anomalies", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert "anomaly_analysis" in data
    analysis = data["anomaly_analysis"]
    assert "unusual_holdings" in analysis
    assert len(analysis["unusual_holdings"]) == 3


def test_get_risk_score_validation():
    """Verify GET /api/v1/ml/risk-score-validation returns Spearman IC & calibration."""
    client = TestClient(app)
    resp = client.get("/api/v1/ml/risk-score-validation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    val = data["score_validation"]
    assert "five_factor_fixed_weights" in val["models"]
    assert "baseline_comparisons" in val


def test_post_comprehensive_insights():
    """Verify POST /api/v1/ml/comprehensive-insights provides the unified tab payload."""
    client = TestClient(app)
    req = {
        "holdings": [
            {"symbol": "RELIANCE", "weight": 0.5},
            {"symbol": "HDFCBANK", "weight": 0.5},
        ]
    }
    resp = client.post("/api/v1/ml/comprehensive-insights", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert "model_statuses" in data
    assert "volatility" in data
    assert "regime" in data
    assert "anomalies" in data
    assert "score_validation" in data
    assert "governance" in data
    assert data["governance"]["is_model_estimate"] is True
    assert "does NOT" in data["governance"]["disclaimer"]


def test_api_validation_error_on_empty_holdings():
    """Verify 422 Unprocessable Entity when holdings are empty or invalid."""
    client = TestClient(app)
    resp = client.post("/api/v1/ml/volatility-forecast", json={"holdings": []})
    assert resp.status_code == 422
