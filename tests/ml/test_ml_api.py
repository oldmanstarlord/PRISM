"""API contract tests for ML risk endpoints under /api/v1/ml/."""

from uuid import UUID

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient

import backend.app.ml.router as ml_router_mod
import backend.app.ml.service as ml_service_mod
from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.main import app


@pytest.fixture(autouse=True)
def mock_price_data(monkeypatch: pytest.MonkeyPatch):
    """Ensure predictable price history during API contract tests."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="B")

    def fake_load_prices(symbols: list[str], session: object, days: int = 500) -> pd.DataFrame:
        data = {}
        for s in symbols:
            ret = rng.normal(0.0004, 0.012, len(dates))
            data[s] = 100.0 * np.cumprod(1.0 + ret)
        return pd.DataFrame(data, index=dates)

    def fake_bench_returns(session: object = None) -> pd.Series:
        return pd.Series(rng.normal(0.0002, 0.009, len(dates)), index=dates)

    monkeypatch.setattr(ml_service_mod, "_load_prices_for_symbols", fake_load_prices)
    monkeypatch.setattr(ml_service_mod, "get_benchmark_returns", fake_bench_returns)
    monkeypatch.setattr(
        ml_router_mod,
        "_get_company_names",
        lambda session, symbols: {symbol: symbol for symbol in symbols},
    )
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=UUID("00000000-0000-0000-0000-000000000001"), email="ml-test@prism.local"
    )
    yield
    app.dependency_overrides.pop(require_user, None)


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
    assert data["status"] == "ready"
    assert "portfolio_forecast" in data
    assert data["portfolio_forecast"]["predicted_volatility_pct"] > 0
    assert "lower_bound_90_pct" in data["portfolio_forecast"]
    assert "upper_bound_90_pct" in data["portfolio_forecast"]
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
    assert "spearman_rank_ic" in val
    assert "isotonic_calibration_curve" in val
    assert len(val["isotonic_calibration_curve"]) == 5


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
