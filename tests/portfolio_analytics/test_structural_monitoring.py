"""Tests for structural monitoring, historical risk persistence, and news intelligence contracts."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.portfolio_analytics.news_signals import generate_modular_news_preview
from backend.app.portfolio_analytics.stock_risk import (
    PortfolioRiskProfile,
)
from backend.app.portfolio_analytics.structural_monitoring import (
    compute_historical_risk_series,
    evaluate_monitoring_indicators,
    load_persisted_risk_history,
    persist_risk_snapshot,
)


@pytest.fixture
def sample_portfolio_profile() -> PortfolioRiskProfile:
    return PortfolioRiskProfile(
        portfolio_risk_score=68.5,
        portfolio_classification="High",
        portfolio_color="#f57c00",
        annualized_volatility=24.5,
        downside_volatility=21.2,
        max_drawdown=18.4,
        portfolio_beta=1.22,
        holding_hhi=0.32,
        effective_holdings=3.12,
        sector_hhi=0.38,
        effective_sectors=2.63,
        diversification_ratio=1.18,
        diversification_score=52.0,
        diversification_grade="C",
        diversification_interpretation="Moderate diversification benefit",
        risk_contributions=[
            {
                "symbol": "TCS",
                "weight_percent": 35.0,
                "risk_contribution_percent": 38.2,
                "sector": "Information Technology",
            },
            {
                "symbol": "INFY",
                "weight_percent": 30.0,
                "risk_contribution_percent": 32.5,
                "sector": "Information Technology",
            },
            {
                "symbol": "HDFCBANK",
                "weight_percent": 35.0,
                "risk_contribution_percent": 29.3,
                "sector": "Financial Services",
            },
        ],
        sector_exposure=[
            {
                "sector": "Information Technology",
                "weight": 65.0,
                "risk_contribution": 70.7,
                "divergence_20d": 1.2,
                "benchmark_target": 25.0,
                "allocation_status": "Excessive",
            },
            {
                "sector": "Financial Services",
                "weight": 35.0,
                "risk_contribution": 29.3,
                "divergence_20d": -0.4,
                "benchmark_target": 25.0,
                "allocation_status": "Elevated",
            },
        ],
        correlation_matrix={
            "TCS": {"TCS": 1.0, "INFY": 0.72, "HDFCBANK": 0.28},
            "INFY": {"TCS": 0.72, "INFY": 1.0, "HDFCBANK": 0.25},
            "HDFCBANK": {"TCS": 0.28, "INFY": 0.25, "HDFCBANK": 1.0},
        },
        historical_risk_trend="Elevating",
        summary_findings=[
            "High IT concentration at 65.0%",
            "Elevated beta of 1.22 vs NIFTY 50",
        ],
    )


@pytest.fixture
def sample_holdings() -> list[dict]:
    return [
        {
            "symbol": "TCS",
            "quantity": 10,
            "buyPrice": 3500.0,
            "companyName": "Tata Consultancy Services",
        },
        {"symbol": "INFY", "quantity": 20, "buyPrice": 1500.0, "companyName": "Infosys Ltd"},
        {"symbol": "HDFCBANK", "quantity": 25, "buyPrice": 1400.0, "companyName": "HDFC Bank Ltd"},
    ]


def test_evaluate_monitoring_indicators_triggers(sample_portfolio_profile, sample_holdings):
    indicators = evaluate_monitoring_indicators(sample_portfolio_profile, [], sample_holdings)
    ind_by_id = {ind.id: ind for ind in indicators}

    # 1. Portfolio risk should trigger (68.5 >= 60)
    assert "IND-PORTFOLIO-RISK" in ind_by_id
    assert ind_by_id["IND-PORTFOLIO-RISK"].triggered is True
    assert ind_by_id["IND-PORTFOLIO-RISK"].severity == "warning"

    # 2. Sector concentration should trigger (65.0% >= 25%)
    assert "IND-SECTOR-CEILING" in ind_by_id
    assert ind_by_id["IND-SECTOR-CEILING"].triggered is True
    assert ind_by_id["IND-SECTOR-CEILING"].severity == "critical"

    # 3. Holding concentration should trigger (TCS is 35k / 100k = 35% >= 20%)
    assert "IND-HOLDING-CONCENTRATION" in ind_by_id
    assert ind_by_id["IND-HOLDING-CONCENTRATION"].triggered is True

    # 4. Effective diversification should trigger (3.12 < 4.0)
    assert "IND-DIVERSIFICATION-LEVEL" in ind_by_id
    assert ind_by_id["IND-DIVERSIFICATION-LEVEL"].triggered is True

    # 5. Downside volatility should trigger (21.2% >= 20.0%)
    assert "IND-DOWNSIDE-VOLATILITY" in ind_by_id
    assert ind_by_id["IND-DOWNSIDE-VOLATILITY"].triggered is True

    # 6. Euler risk share should trigger (38.2% >= 30.0%)
    assert "IND-EULER-RISK-SHARE" in ind_by_id
    assert ind_by_id["IND-EULER-RISK-SHARE"].triggered is True


def test_compute_historical_risk_series(sample_portfolio_profile, sample_holdings):
    series = compute_historical_risk_series(sample_holdings, sample_portfolio_profile)
    assert len(series) == 4
    assert series[0].lookback_window == "Current (252d)"
    assert series[0].portfolio_risk_score == 68.5

    # Since trend is Elevating, 1M ago should be lower
    assert series[1].lookback_window == "1 Month Ago (-21d)"
    assert series[1].portfolio_risk_score < series[0].portfolio_risk_score
    assert series[1].coverage_status == "full"


def test_persist_and_load_risk_history():
    dummy_snapshot = {
        "portfolio_risk_score": 45.0,
        "portfolio_classification": "Moderate",
        "annualized_volatility": 18.2,
        "downside_volatility": 14.1,
        "max_drawdown": 12.0,
        "diversification_score": 75.0,
        "top_sector": "Financial Services",
        "indicators": [{"id": "IND-1"}],
    }
    count = persist_risk_snapshot(dummy_snapshot)
    assert count >= 1

    loaded = load_persisted_risk_history()
    assert len(loaded) >= 1
    last = loaded[-1]
    assert last["portfolio_risk_score"] == 45.0
    assert last["top_sector"] == "Financial Services"


def test_generate_modular_news_preview(sample_holdings):
    preview = generate_modular_news_preview(sample_holdings)
    assert preview.contract_version == "v1-modular-draft"
    assert "Decoupled" in preview.architecture_status
    assert len(preview.stock_signals) == 3

    for sig in preview.stock_signals:
        assert sig.symbol in ["TCS", "INFY", "HDFCBANK"]
        assert -1.0 <= sig.sentiment_average_7d <= 1.0
        assert sig.sentiment_label in ["positive", "neutral", "negative"]
        assert sig.news_risk_multiplier >= 0.5


def test_api_structural_monitoring_endpoint(sample_portfolio_profile):
    client = TestClient(app)
    payload = {
        "holdings": [
            {"symbol": "TCS", "quantity": 10, "buyPrice": 3500.0, "companyName": "TCS"},
            {"symbol": "INFY", "quantity": 15, "buyPrice": 1500.0, "companyName": "Infosys"},
            {"symbol": "RELIANCE", "quantity": 8, "buyPrice": 2800.0, "companyName": "Reliance"},
        ]
    }
    with patch(
        "backend.app.portfolio_analytics.router.calculate_portfolio_comprehensive_risk",
        return_value=([], sample_portfolio_profile),
    ):
        resp = client.post("/api/v1/portfolio-analysis/structural-monitoring", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_risk_score" in data
    assert "indicators" in data
    assert len(data["indicators"]) >= 5
    assert "historical_risk_series" in data
    assert len(data["historical_risk_series"]) == 4
    assert "largest_risk_contributors" in data
    assert "disclaimer" in data


def test_api_risk_history_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/portfolio-analysis/risk-history")
    assert resp.status_code == 410
    assert "authenticated" in resp.json()["detail"]


def test_api_news_signals_endpoint():
    client = TestClient(app)
    payload = {
        "holdings": [
            {"symbol": "TCS", "quantity": 10, "buyPrice": 3500.0},
            {"symbol": "INFY", "quantity": 20, "buyPrice": 1500.0},
        ]
    }
    resp = client.post("/api/v1/portfolio-analysis/news-signals", json=payload)
    assert resp.status_code == 401
