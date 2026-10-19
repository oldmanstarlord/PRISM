"""Unit tests for explainable stock-level risk, portfolio risk, and diversification index."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.portfolio_analytics.stock_risk import (
    _classify_risk,
    _normalize_factor,
    calculate_single_window_metrics,
    calculate_stock_risk,
)

client = TestClient(app)


def test_normalize_factor():
    # Value below low bound clips to 0
    assert _normalize_factor(0.05, 0.10, 0.40) == 0.0
    # Value above high bound clips to 100
    assert _normalize_factor(0.50, 0.10, 0.40) == 100.0
    # Midpoint normalizes to 50
    assert _normalize_factor(0.25, 0.10, 0.40) == 50.0
    # Inverted flag reverses score
    assert _normalize_factor(0.25, 0.10, 0.40, invert=True) == 50.0
    assert _normalize_factor(0.05, 0.10, 0.40, invert=True) == 100.0


def test_classify_risk():
    assert _classify_risk(15.0)[0] == "Low"
    assert _classify_risk(45.0)[0] == "Moderate"
    assert _classify_risk(65.0)[0] == "High"
    assert _classify_risk(85.0)[0] == "Very High"


def test_single_window_metrics_calculation():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(100)]
    # Create deterministic mock returns
    np.random.seed(42)
    stock_ret = pd.Series(np.random.normal(0.0005, 0.015, 100), index=dates)
    bench_ret = pd.Series(np.random.normal(0.0003, 0.010, 100), index=dates)

    metrics = calculate_single_window_metrics(stock_ret, bench_ret, 63, "3M")
    assert metrics.window == "3M"
    assert metrics.observations == 63
    assert metrics.annualized_volatility > 0.10
    assert metrics.downside_volatility > 0.05
    assert metrics.max_drawdown >= 0.0
    assert isinstance(metrics.beta, float)
    assert isinstance(metrics.alpha, float)


def test_calculate_stock_risk_explainable_scoring():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(150)]
    # Simulate a steady stock with 15% annual volatility
    base_price = 1000.0
    prices = [base_price]
    for _ in range(149):
        prices.append(prices[-1] * (1 + np.random.normal(0.0002, 0.01)))
    prices_series = pd.Series(prices, index=dates)
    bench_returns = pd.Series(np.random.normal(0.0001, 0.008, 150), index=dates)

    profile = calculate_stock_risk(
        symbol="TCS",
        prices_series=prices_series,
        benchmark_returns=bench_returns,
        holding_info={
            "companyName": "Tata Consultancy Services Ltd.",
            "sector": "Information Technology",
            "buyPrice": 950.0,
            "buyDate": "2026-01-15",
            "quantity": 10,
        },
    )

    assert profile.symbol == "TCS"
    assert 0 <= profile.overall_score <= 100
    assert profile.risk_classification in {"Low", "Moderate", "High", "Very High"}
    assert len(profile.factors) == 5
    assert profile.purchase_price == 950.0
    assert profile.unrealized_return is not None
    assert len(profile.primary_drivers) > 0
    assert len(profile.narrative_explanation) > 10
    assert "Assessed as" in profile.narrative_explanation


def test_comprehensive_risk_api_endpoint():
    payload = {
        "holdings": [
            {
                "symbol": "TCS",
                "companyName": "Tata Consultancy Services Ltd.",
                "sector": "Technology",
                "quantity": 10,
                "buyPrice": 2500.0,
                "buyDate": "2026-01-15",
            },
            {
                "symbol": "INFY",
                "companyName": "Infosys Ltd.",
                "sector": "Technology",
                "quantity": 20,
                "buyPrice": 1200.0,
                "buyDate": "2026-02-01",
            },
        ]
    }

    response = client.post("/api/v1/portfolio-analysis/comprehensive-risk", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "stock_profiles" in data
    assert "portfolio_profile" in data
    assert len(data["stock_profiles"]) == 2

    p_prof = data["portfolio_profile"]
    assert 0 <= p_prof["portfolio_risk_score"] <= 100
    assert p_prof["portfolio_classification"] in {"Low", "Moderate", "High", "Very High"}
    assert p_prof["annualized_volatility"] > 0
    assert p_prof["effective_holdings"] > 0
    assert p_prof["diversification_score"] >= 0
    assert p_prof["diversification_grade"] in {"A", "B", "C", "D"}
    assert len(p_prof["risk_contributions"]) == 2
    assert len(p_prof["sector_exposure"]) >= 1


def test_single_stock_portfolio_risk_handling():
    payload = {
        "holdings": [
            {
                "symbol": "RELIANCE",
                "companyName": "Reliance Industries Ltd.",
                "sector": "Energy",
                "quantity": 10,
                "buyPrice": 1200.0,
            }
        ]
    }
    response = client.post("/api/v1/portfolio-analysis/comprehensive-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["stock_profiles"]) == 1
    assert data["portfolio_profile"]["effective_holdings"] == 1.0


def test_insufficient_history_handling():
    # Only 5 observations (well below minimum horizon)
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(5)]
    stock_ret = pd.Series([0.01, -0.02, 0.005, -0.01, 0.015], index=dates)
    bench_ret = pd.Series([0.005, -0.01, 0.002, -0.005, 0.008], index=dates)

    metrics = calculate_single_window_metrics(stock_ret, bench_ret, 21, "1M")
    assert metrics.observations == 5
    # Should safely return default bounded metrics without crashing
    assert metrics.annualized_volatility == 0.0
    assert metrics.beta == 1.0


def test_extreme_market_movements_scoring():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(120)]
    # Simulate an extreme 60% crash
    prices = [1000.0]
    for i in range(119):
        factor = 0.98 if i < 40 else (0.97 if i < 80 else 1.01)
        prices.append(prices[-1] * factor)
    prices_series = pd.Series(prices, index=dates)
    bench_returns = pd.Series([0.0001] * 120, index=dates)

    profile = calculate_stock_risk(
        symbol="HIGHCRASH",
        prices_series=prices_series,
        benchmark_returns=bench_returns,
        holding_info={
            "buyPrice": 1000.0,
            "quantity": 5,
            "buyDate": "2026-01-01",
        },
    )
    # Risk score must be in High or Very High range and capped at 100
    assert profile.risk_classification in {"High", "Very High"}
    assert profile.overall_score >= 65.0
    assert profile.overall_score <= 100.0
    assert any("drawdown" in d.lower() or "volatility" in d.lower() for d in profile.primary_drivers)
    assert profile.unrealized_return is not None
    assert profile.unrealized_return < -50.0
    assert profile.unrealized_pnl is not None
    assert profile.unrealized_pnl < 0.0


def test_empty_and_zero_portfolio_handling():
    from backend.app.db.session import get_session
    from backend.app.portfolio_analytics.stock_risk import calculate_portfolio_comprehensive_risk

    session = next(get_session())
    try:
        # Empty holdings list
        stock_profiles, port_profile = calculate_portfolio_comprehensive_risk([], session)
        assert len(stock_profiles) == 0
        assert port_profile.portfolio_risk_score == 0.0
        assert port_profile.effective_holdings == 0.0
        assert port_profile.diversification_score == 0.0

        # Zero-value holdings (quantity = 0 or buyPrice = 0)
        stock_profiles_zero, port_profile_zero = calculate_portfolio_comprehensive_risk(
            [{"symbol": "TCS", "quantity": 0, "buyPrice": 0}], session
        )
        assert len(stock_profiles_zero) == 1
        assert port_profile_zero.portfolio_risk_score >= 0.0
    finally:
        session.close()


def test_sector_exposure_benchmarks_and_allocation():
    payload = {
        "holdings": [
            {
                "symbol": "TCS",
                "companyName": "Tata Consultancy Services Ltd.",
                "sector": "Information Technology",
                "quantity": 40,
                "buyPrice": 3000.0,
            },
            {
                "symbol": "INFY",
                "companyName": "Infosys Ltd.",
                "sector": "Information Technology",
                "quantity": 40,
                "buyPrice": 1500.0,
            },
            {
                "symbol": "RELIANCE",
                "companyName": "Reliance Industries Ltd.",
                "sector": "Energy",
                "quantity": 10,
                "buyPrice": 2000.0,
            },
        ]
    }
    response = client.post("/api/v1/portfolio-analysis/comprehensive-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    sectors = data["portfolio_profile"]["sector_exposure"]

    it_sector = next((s for s in sectors if s["sector"] == "Information Technology"), None)
    assert it_sector is not None
    assert it_sector["weight"] > 50.0
    assert it_sector["benchmark_target"] == 25.0
    assert it_sector["allocation_status"] == "Excessive"

    # Euler risk contribution shares should sum to approximately 100%
    risk_shares = [rc["risk_contribution_share"] for rc in data["portfolio_profile"]["risk_contributions"]]
    assert abs(sum(risk_shares) - 100.0) < 2.0

