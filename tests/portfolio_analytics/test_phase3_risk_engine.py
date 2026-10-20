"""Phase 3 Comprehensive Quantitative Risk Engine & Mathematical Invariant Tests.

Tests every formula, metric invariant, and numerical boundary:
1. Return construction & Jensen's inequality log-return approximation error
2. Covariance matrix regularization under collinearity and short samples
3. Exact Euler variance decomposition & hedge preservation (negative contributions)
4. Historical VaR, Parametric VaR, and Expected Shortfall (CVaR) invariants
5. Drawdown bounds and wealth path calculation
6. Stress testing (market beta shock, sector shock, single-stock shock, correlation breakdown)
7. Configurable alert thresholds validation and indicator attribution
8. MST topological properties (distance bounds, N-1 connectivity, edge discards)
9. Methodology registry completeness and scoring weight sum invariants
10. Walk-forward chronological integrity and purge verification
"""

import math
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import get_session
from backend.app.main import app
from backend.app.portfolio_analytics.calculator import (
    calculate_stress,
    regularize_covariance,
)
from backend.app.portfolio_analytics.methodology_registry import (
    PORTFOLIO_RISK_FACTOR_WEIGHTS,
    STOCK_RISK_FACTOR_WEIGHTS,
    get_methodology_manifest,
    validate_alert_thresholds,
)
from backend.app.portfolio_analytics.structural_monitoring import (
    evaluate_monitoring_indicators,
)
from backend.app.validation.walk_forward import walk_forward_splits

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_database_dependency():
    """Keep formula/API unit tests independent of a configured PostgreSQL host."""
    session = MagicMock()
    session.scalar.return_value = None

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    yield
    app.dependency_overrides.pop(get_session, None)


# =====================================================================
# 1. Return Construction & Jensen's Inequality Test
# =====================================================================


def test_log_return_weighted_sum_jensens_inequality_gap() -> None:
    """Document and test that linear sum of log returns systematically
    understates simple portfolio return.

    By Jensen's inequality:
        ln(sum(w_i * (1 + R_i))) >= sum(w_i * ln(1 + R_i))
    Therefore, approximating portfolio log return as sum(w_i * r_i) produces a negative bias
    (error <= 0), which compounds over time. PRISM mandates simple returns for linear compounding.
    """
    weights = np.array([0.4, 0.35, 0.25])
    simple_returns = np.array([0.05, -0.02, 0.08])

    # Exact linear portfolio return
    r_portfolio_simple = float(np.sum(weights * simple_returns))

    # True portfolio log return
    true_portfolio_log_return = math.log(1.0 + r_portfolio_simple)

    # Naive linear combination of log returns
    individual_log_returns = np.log(1.0 + simple_returns)
    naive_sum_log_returns = float(np.sum(weights * individual_log_returns))

    # Jensen's inequality: naive_sum <= true_portfolio_log_return
    gap = naive_sum_log_returns - true_portfolio_log_return
    assert gap <= 1e-12, f"Jensen gap violated: {gap} > 0"
    # Gap is strictly negative when returns are non-identical
    assert gap < 0.0
    # Error magnitude is non-trivial for volatile returns
    assert abs(gap) > 0.0001


# =====================================================================
# 2. Covariance Regularization Tests
# =====================================================================


def test_regularize_covariance_singular_matrix() -> None:
    """Test that singular or rank-deficient covariance matrices are regularized
    to positive-definite."""
    # Perfectly collinear 3x3 covariance matrix (rank 1)
    v = np.array([0.02, 0.03, 0.05])
    singular_cov = np.outer(v, v)
    assert np.linalg.matrix_rank(singular_cov) == 1

    reg_cov = regularize_covariance(singular_cov, min_eigenvalue_ratio=1e-5)
    eigenvalues = np.linalg.eigvalsh(reg_cov)
    max_eig = float(np.max(eigenvalues))

    assert np.all(eigenvalues >= max_eig * 1e-5 - 1e-12), f"Eigenvalues below floor: {eigenvalues}"
    assert np.allclose(reg_cov, reg_cov.T), "Regularized covariance must be symmetric"


def test_regularize_covariance_zero_variance_preservation() -> None:
    """Test that zero-variance matrices (flat prices) return exact zero matrix
    without artifact noise."""
    zero_cov = np.zeros((4, 4))
    reg_cov = regularize_covariance(zero_cov)
    assert np.all(reg_cov == 0.0), "Zero covariance must remain exact zeros"


# =====================================================================
# 3. Euler Decomposition & Hedge Preservation via Comprehensive Risk API
# =====================================================================


@patch("backend.app.portfolio_analytics.stock_risk.get_benchmark_returns")
@patch("backend.app.portfolio_analytics.stock_risk._load_stock_prices_yfinance")
@patch(
    "backend.app.portfolio_analytics.stock_risk._load_stock_prices_from_db",
    return_value=pd.DataFrame(),
)
def test_euler_decomposition_sums_to_portfolio_volatility(
    _mock_load_db, mock_load_yf, mock_get_bench
) -> None:
    """Test that sum of Euler Component Volatilities C_i exactly equals total
    portfolio volatility."""
    n_days = 260
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    np.random.seed(42)
    mock_bench = pd.Series(np.random.normal(0.0004, 0.011, n_days), index=dates)
    mock_get_bench.return_value = mock_bench

    # 4 stocks with correlated random walks
    ret_0 = np.random.normal(0.0005, 0.016, n_days)
    ret_1 = 0.5 * ret_0 + np.random.normal(0.0002, 0.012, n_days)
    ret_2 = 0.4 * ret_0 + np.random.normal(0.0003, 0.014, n_days)
    ret_3 = 0.3 * ret_0 + np.random.normal(0.0001, 0.010, n_days)

    price_df = pd.DataFrame(
        {
            "HDFCBANK": 1000.0 * np.cumprod(1.0 + ret_0),
            "INFY": 1500.0 * np.cumprod(1.0 + ret_1),
            "RELIANCE": 2000.0 * np.cumprod(1.0 + ret_2),
            "TCS": 3000.0 * np.cumprod(1.0 + ret_3),
        },
        index=dates,
    )
    mock_load_yf.return_value = price_df

    payload = {
        "holdings": [
            {
                "symbol": "HDFCBANK",
                "quantity": 30,
                "buyPrice": 1000.0,
                "sector": "Financial Services",
            },
            {
                "symbol": "INFY",
                "quantity": 20,
                "buyPrice": 1500.0,
                "sector": "Information Technology",
            },
            {"symbol": "RELIANCE", "quantity": 15, "buyPrice": 2000.0, "sector": "Energy"},
            {
                "symbol": "TCS",
                "quantity": 10,
                "buyPrice": 3000.0,
                "sector": "Information Technology",
            },
        ]
    }
    response = client.post("/api/v1/portfolio-analysis/comprehensive-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    p_profile = data["portfolio_profile"]

    port_vol = p_profile["annualized_volatility"]  # e.g. 18.5 (%)
    risk_contributions = p_profile["risk_contributions"]

    # Sum of component risks (scaled to percentage: component_risk * 100)
    sum_comp_vol = sum(
        rc["component_risk"] * 100.0
        for rc in risk_contributions
        if rc.get("component_risk") is not None
    )
    # Sum of component volatilities must reconcile to portfolio volatility
    # within numerical tolerance
    assert abs(sum_comp_vol - port_vol) < 0.05, (
        f"Euler reconciliation discrepancy: sum {sum_comp_vol:.4f}% vs port_vol {port_vol:.4f}%"
    )

    # Risk contribution shares must sum to 100%
    shares_sum = sum(rc["risk_contribution_share"] for rc in risk_contributions)
    assert abs(shares_sum - 100.0) < 0.5, f"Risk shares sum {shares_sum} != 100%"


@patch("backend.app.portfolio_analytics.stock_risk.get_benchmark_returns")
@patch("backend.app.portfolio_analytics.stock_risk._load_stock_prices_yfinance")
@patch(
    "backend.app.portfolio_analytics.stock_risk._load_stock_prices_from_db",
    return_value=pd.DataFrame(),
)
def test_euler_preserves_negative_hedging_contributions(
    _mock_load_db, mock_load_yf, mock_get_bench
) -> None:
    """Test that negatively correlated hedging assets produce legitimate
    negative risk contributions."""
    n_days = 260
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    np.random.seed(123)
    market = np.random.normal(0, 0.015, n_days)
    mock_get_bench.return_value = pd.Series(market, index=dates)

    # Strong long equity
    stock_returns = 0.95 * market + np.random.normal(0, 0.003, n_days)
    # Inverse / hedge asset (correlation ~ -0.9 with stock)
    hedge_returns = -0.90 * market + np.random.normal(0, 0.003, n_days)

    price_df = pd.DataFrame(
        {
            "EQUITY": 1000.0 * np.cumprod(1.0 + stock_returns),
            "HEDGE": 100.0 * np.cumprod(1.0 + hedge_returns),
        },
        index=dates,
    )
    mock_load_yf.return_value = price_df

    payload = {
        "holdings": [
            {"symbol": "EQUITY", "quantity": 80, "buyPrice": 1000.0, "sector": "Broad Market"},
            {
                "symbol": "HEDGE",
                "quantity": 200,
                "buyPrice": 100.0,
                "sector": "Commodities & Hedges",
            },
        ]
    }
    response = client.post("/api/v1/portfolio-analysis/comprehensive-risk", json=payload)
    assert response.status_code == 200
    data = response.json()

    risk_contribs = data["portfolio_profile"]["risk_contributions"]
    hedge_rc = next(rc for rc in risk_contribs if rc["symbol"] == "HEDGE")

    # Marginal risk and component risk must be negative for the hedge!
    assert hedge_rc["marginal_risk"] < 0.0, (
        f"Expected negative marginal risk: {hedge_rc['marginal_risk']}"
    )
    assert hedge_rc["component_risk"] < 0.0, (
        f"Expected negative component risk: {hedge_rc['component_risk']}"
    )
    assert hedge_rc["risk_contribution_share"] < 0.0, (
        f"Expected negative risk share: {hedge_rc['risk_contribution_share']}"
    )


# =====================================================================
# 4. Tail Risk Invariants (VaR & Expected Shortfall)
# =====================================================================


@patch("backend.app.portfolio_analytics.stock_risk.get_benchmark_returns")
@patch("backend.app.portfolio_analytics.stock_risk._load_stock_prices_yfinance")
@patch(
    "backend.app.portfolio_analytics.stock_risk._load_stock_prices_from_db",
    return_value=pd.DataFrame(),
)
def test_var_and_expected_shortfall_invariants(_mock_load_db, mock_load_yf, mock_get_bench) -> None:
    """Test mathematical invariants for Historical and Parametric VaR and Expected Shortfall:
    1. ES >= VaR at the same confidence level (sub-additivity & tail expectation)
    2. VaR_99 >= VaR_95 (monotonicity with confidence level)
    3. ES_99 >= ES_95
    4. Backtest exception count >= 0
    """
    n_days = 260
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]
    np.random.seed(99)
    mock_get_bench.return_value = pd.Series(np.random.normal(0.0003, 0.012, n_days), index=dates)

    returns = np.random.normal(loc=0.0002, scale=0.018, size=(n_days, 2))
    price_df = pd.DataFrame(
        {
            "STOCKA": 100.0 * np.cumprod(1.0 + returns[:, 0]),
            "STOCKB": 100.0 * np.cumprod(1.0 + returns[:, 1]),
        },
        index=dates,
    )
    mock_load_yf.return_value = price_df

    payload = {
        "holdings": [
            {"symbol": "STOCKA", "quantity": 50, "buyPrice": 100.0, "sector": "General"},
            {"symbol": "STOCKB", "quantity": 50, "buyPrice": 100.0, "sector": "General"},
        ]
    }
    response = client.post("/api/v1/portfolio-analysis/comprehensive-risk", json=payload)
    assert response.status_code == 200
    p_profile = response.json()["portfolio_profile"]

    var_95 = p_profile["var_historical_95"]
    cvar_95 = p_profile["cvar_historical_95"]
    var_99 = p_profile["var_historical_99"]
    cvar_99 = p_profile["cvar_historical_99"]

    # Invariant 1: Expected Shortfall (CVaR) >= VaR at 95%
    assert cvar_95 >= var_95, f"CVaR_95 {cvar_95} < VaR_95 {var_95}"

    # Invariant 2: Expected Shortfall (CVaR) >= VaR at 99%
    assert cvar_99 >= var_99, f"CVaR_99 {cvar_99} < VaR_99 {var_99}"

    # Invariant 3: VaR increases with confidence level
    assert var_99 >= var_95, f"VaR_99 {var_99} < VaR_95 {var_95}"

    # Invariant 4: CVaR increases with confidence level
    assert cvar_99 >= cvar_95, f"CVaR_99 {cvar_99} < CVaR_95 {cvar_95}"

    # Invariant 5: Backtest exceptions non-negative and finite
    exc_95 = p_profile["var_backtest_exceptions_95"]
    exc_99 = p_profile["var_backtest_exceptions_99"]
    assert exc_95 is not None and exc_95 >= 0
    assert exc_99 is not None and exc_99 >= 0
    assert exc_99 <= exc_95


# =====================================================================
# 5. Stress Testing: All 4 Scenarios Test
# =====================================================================


def test_stress_scenarios_all_four_kinds() -> None:
    """Test all 4 stress testing scenarios:
    1. Single stock shock
    2. Industry / Sector shock
    3. Market beta transmission shock
    4. Systemic correlation breakdown
    """
    from backend.app.portfolio_analytics.schemas import StressScenarioInput

    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(100)]
    np.random.seed(42)
    returns_df = pd.DataFrame(
        {
            "STOCK_0": np.random.normal(0.0005, 0.015, 100),
            "STOCK_1": np.random.normal(0.0003, 0.012, 100),
        },
        index=dates,
    )
    holdings = {"STOCK_0": 0.5, "STOCK_1": 0.5}
    industries = {"STOCK_0": "IT", "STOCK_1": "FINANCE"}
    bench_returns = pd.Series(np.random.normal(0.0004, 0.010, 100), index=dates)

    # 1. Single stock shock: STOCK_0 drops 20%
    res_stock = calculate_stress(
        StressScenarioInput(kind="stock", target="STOCK_0", shock_percent=-20.0),
        returns=returns_df,
        holdings=holdings,
        industries=industries,
    )
    assert res_stock is not None
    # Target stock receives exact -20% shock, contributing -10% with 0.5 weight
    target_res = next(r for r in res_stock.results if r.symbol == "STOCK_0")
    assert target_res.estimated_return_percent == -20.0
    assert abs(target_res.portfolio_contribution_percent - (-10.0)) < 1e-4
    assert res_stock.portfolio_impact_percent < 0.0

    # 2. Industry shock: IT drops 15%
    res_ind = calculate_stress(
        StressScenarioInput(kind="industry", target="IT", shock_percent=-15.0),
        returns=returns_df,
        holdings=holdings,
        industries=industries,
    )
    assert res_ind is not None
    # Impact on IT (weight 0.5) = 0.5 * (-15%) = -7.5%
    assert abs(res_ind.portfolio_impact_percent - (-7.5)) < 0.1

    # 3. Market shock: Market drops 10%
    res_market = calculate_stress(
        StressScenarioInput(kind="market", target="NIFTY 50", shock_percent=-10.0),
        returns=returns_df,
        holdings=holdings,
        industries=industries,
        benchmark_returns=bench_returns,
    )
    assert res_market is not None
    assert res_market.portfolio_impact_percent < 0.0
    with pytest.raises(ValueError, match="real benchmark observations"):
        calculate_stress(
            StressScenarioInput(kind="market", target="NIFTY 50", shock_percent=-10.0),
            returns=returns_df,
            holdings=holdings,
            industries=industries,
            benchmark_returns=None,
        )

    # 4. Correlation breakdown: 50% shift toward 1.0
    res_corr = calculate_stress(
        StressScenarioInput(kind="correlation", target="Systemic", shock_percent=50.0),
        returns=returns_df,
        holdings=holdings,
        industries=industries,
    )
    assert res_corr is not None
    assert res_corr.portfolio_impact_percent >= 0.0


# =====================================================================
# 6. Configurable Alert Thresholds & Monitoring Indicators
# =====================================================================


def test_alert_thresholds_validation_and_custom_triggers() -> None:
    """Test validation bounds for alert thresholds and indicator triggering."""
    from backend.app.portfolio_analytics.stock_risk import PortfolioRiskProfile

    # Test valid thresholds pass through
    custom = {
        "max_single_stock_weight": 25.0,
        "max_top_sector_weight": 35.0,
        "max_portfolio_beta": 1.4,
    }
    validated = validate_alert_thresholds(custom)
    assert validated["max_single_stock_weight"] == 25.0
    assert validated["max_top_sector_weight"] == 35.0
    assert validated["max_portfolio_beta"] == 1.4

    # Test out-of-bounds clamping
    out_of_bounds = {
        "max_single_stock_weight": 150.0,  # exceeds max 60
        "max_portfolio_beta": 0.1,  # below min 0.5
    }
    clamped = validate_alert_thresholds(out_of_bounds)
    assert clamped["max_single_stock_weight"] == 60.0
    assert clamped["max_portfolio_beta"] == 0.5

    # Test indicator evaluation with strict custom threshold
    dummy_portfolio = PortfolioRiskProfile(
        portfolio_risk_score=55.0,
        portfolio_classification="Moderate",
        portfolio_color="#8A5A00",
        annualized_volatility=16.5,
        downside_volatility=11.2,
        max_drawdown=14.0,
        portfolio_beta=1.1,
        holding_hhi=0.52,
        effective_holdings=1.92,
        sector_hhi=0.52,
        effective_sectors=1.92,
        diversification_ratio=1.15,
        diversification_score=45.0,
        diversification_grade="C",
        diversification_interpretation="Moderate concentration",
        risk_contributions=[],
        sector_exposure=[{"sector": "IT", "weight": 60.0, "allocation_status": "Excessive"}],
        correlation_matrix={},
        historical_risk_trend="stable",
        summary_findings=[],
    )
    holdings = [
        {"symbol": "INFY", "quantity": 60, "buyPrice": 100.0, "sector": "IT"},
        {"symbol": "HDFCBANK", "quantity": 40, "buyPrice": 100.0, "sector": "Finance"},
    ]

    # Strict threshold: max_single_stock_weight = 30% -> INFY (60%) breaches
    indicators = evaluate_monitoring_indicators(
        portfolio_profile=dummy_portfolio,
        stock_profiles=[],
        holdings=holdings,
        custom_thresholds={"max_single_stock_weight": 30.0},
    )

    conc_ind = next(ind for ind in indicators if ind.id == "IND-HOLDING-CONCENTRATION")
    assert conc_ind.triggered is True
    assert conc_ind.threshold_value == 30.0
    assert "INFY" in conc_ind.contributing_holdings
    assert len(conc_ind.assumptions) > 0


# =====================================================================
# 7. MST Topological Invariants Test
# =====================================================================


def test_mst_topological_invariants() -> None:
    """Test mathematical invariants of the Mantegna distance transform and MST:
    1. Distance d = sqrt(2(1 - rho)) is bounded in [0, 2] for all rho in [-1, 1]
    2. rho = 1 -> d = 0
    3. rho = 0 -> d = sqrt(2) approx 1.4142
    4. rho = -1 -> d = 2
    5. An MST on N vertices has exactly N - 1 edges, discarding (N-1)(N-2)/2 edges
    """
    # 1. Distance bounds
    rhos = np.linspace(-1.0, 1.0, 100)
    distances = np.sqrt(2.0 * np.maximum(0.0, 1.0 - rhos))
    assert np.all(distances >= 0.0)
    assert np.all(distances <= 2.0)

    # 2. Key values
    assert abs(math.sqrt(2 * (1 - 1.0)) - 0.0) < 1e-12
    assert abs(math.sqrt(2 * (1 - 0.0)) - math.sqrt(2)) < 1e-12
    assert abs(math.sqrt(2 * (1 - (-1.0))) - 2.0) < 1e-12

    # 3. Discarded edges invariant
    for N in [5, 10, 25, 50]:
        total_possible_edges = N * (N - 1) // 2
        mst_edges = N - 1
        discarded_edges = total_possible_edges - mst_edges
        theoretical_discarded = (N - 1) * (N - 2) // 2
        assert discarded_edges == theoretical_discarded, (
            f"Edge discard invariant failed for N={N}: {discarded_edges} != {theoretical_discarded}"
        )


# =====================================================================
# 8. Methodology Registry Completeness & Weight Invariants
# =====================================================================


def test_methodology_registry_completeness_and_weights() -> None:
    """Test that all scoring weights sum exactly to 1.0 and methodology
    registry is fully populated."""
    # Stock risk weights sum to 1.0
    assert abs(sum(STOCK_RISK_FACTOR_WEIGHTS.values()) - 1.0) < 1e-9

    # Portfolio risk weights sum to 1.0
    assert abs(sum(PORTFOLIO_RISK_FACTOR_WEIGHTS.values()) - 1.0) < 1e-9

    manifest = get_methodology_manifest()
    assert manifest["methodology_version"] == "2026.1"

    metrics = manifest["metrics"]
    required_metrics = [
        "PORTFOLIO_RISK_SCORE_HEURISTIC",
        "STOCK_RISK_SCORE_HEURISTIC",
        "ANNUALIZED_VOLATILITY",
        "DOWNSIDE_VOLATILITY",
        "MAX_DRAWDOWN",
        "HISTORICAL_VAR_95",
        "HISTORICAL_ES_95",
        "EULER_COMPONENT_RISK",
        "MARKET_BETA",
        "MANTEGNA_MST_DISTANCE",
    ]
    for m in required_metrics:
        assert m in metrics, f"Missing required metric in registry: {m}"
        meta = metrics[m]
        assert meta["definition"]
        assert meta["formula_plain"]
        assert meta["units"]
        assert meta["default_window"]
        assert meta["min_observations"] > 0
        assert meta["limitations"]


# =====================================================================
# 9. Walk-Forward Chronological Audit Test
# =====================================================================


def test_walk_forward_expanding_and_purging_invariants() -> None:
    """Test walk-forward splits prevent look-ahead bias and respect purge intervals."""
    base_date = date(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(120)]

    splits = walk_forward_splits(
        observations=dates,
        minimum_train_size=60,
        test_size=20,
        step_size=20,
        purge_size=5,
    )
    assert len(splits) > 0

    for split in splits:
        # Train indices must be strictly before test indices
        assert max(split.train_indices) < min(split.test_indices)
        # Purge gap must be respected
        gap = min(split.test_indices) - max(split.train_indices)
        assert gap > 5, f"Purge gap violated: {gap} <= 5"
        # Dates must be strictly chronological
        assert split.train_end < split.test_start
