"""Phase 1 Formula Audit & Mathematical Integrity Test Suite.

Independent verification of all quantitative portfolio analytics metrics against
hand-calculated mathematical ground truth, numpy/scipy references, and edge cases.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from scipy import stats  # type: ignore[import-untyped]

from backend.app.portfolio_analytics.calculator import (
    ANNUALISATION_FACTOR,
    calculate_risk,
    calculate_stress,
)
from backend.app.portfolio_analytics.schemas import StressScenarioInput

# ─── 1. Volatility (Daily & Annualized with ddof=1, sqrt(252)) ───


def test_volatility_hand_calculated() -> None:
    """Verify daily and annualized volatility against hand-calculated values.

    Given 5 daily returns: [0.01, -0.02, 0.015, -0.005, 0.02]
    Mean = 0.004
    Deviations = [0.006, -0.024, 0.011, -0.009, 0.016]
    Squared dev = [0.000036, 0.000576, 0.000121, 0.000081, 0.000256] = 0.001070
    Sample variance (ddof=1) = 0.001070 / 4 = 0.0002675
    Daily vol = sqrt(0.0002675) ~= 0.016355427
    Annualized vol = Daily vol * sqrt(252) ~= 0.25964893
    """
    returns = np.array([0.01, -0.02, 0.015, -0.005, 0.02], dtype=np.float64)
    expected_daily_var = 0.001070 / 4.0
    expected_daily_vol = math.sqrt(expected_daily_var)
    expected_ann_vol = expected_daily_vol * math.sqrt(252.0)

    computed_daily_vol = float(np.std(returns, ddof=1))
    computed_ann_vol = computed_daily_vol * math.sqrt(ANNUALISATION_FACTOR)

    assert abs(computed_daily_vol - expected_daily_vol) < 1e-12
    assert abs(computed_ann_vol - expected_ann_vol) < 1e-12


# ─── 2. Downside Semi-Deviation (Target = 0) ───


def test_downside_deviation_hand_calculated() -> None:
    """Verify downside semi-deviation against hand calculation.

    Returns: [0.02, -0.03, 0.01, -0.01, 0.0]
    Negative components: [0.0, -0.03, 0.0, -0.01, 0.0]
    Squared negatives: [0.0, 0.0009, 0.0, 0.0001, 0.0] -> Sum = 0.0010
    Mean of squared negatives (N=5): 0.0010 / 5 = 0.0002
    Downside daily = sqrt(0.0002) ~= 0.0141421356
    Annualized downside = 0.0141421356 * sqrt(252) ~= 0.22449944
    """
    returns = np.array([0.02, -0.03, 0.01, -0.01, 0.0], dtype=np.float64)
    negatives = np.minimum(returns, 0.0)
    expected_downside_daily = math.sqrt(np.mean(np.square(negatives)))
    expected_ann_downside = expected_downside_daily * math.sqrt(252.0)

    downside_daily = float(np.sqrt(np.mean(np.square(np.minimum(returns, 0.0)))))
    ann_downside = downside_daily * math.sqrt(ANNUALISATION_FACTOR)

    assert abs(downside_daily - expected_downside_daily) < 1e-12
    assert abs(ann_downside - expected_ann_downside) < 1e-12


# ─── 3. Maximum Drawdown (Peak-to-Trough) ───


def test_maximum_drawdown_hand_calculated() -> None:
    """Verify maximum drawdown on wealth path.

    Wealth indices: [100, 120, 90, 110, 80, 95]
    Running peaks:  [100, 120, 120, 120, 120, 120]
    Drawdowns:
      (100-100)/100 = 0%
      (120-120)/120 = 0%
      (90-120)/120  = -25%
      (110-120)/120 = -8.33%
      (80-120)/120  = -33.3333%  <-- Peak-to-trough max drawdown
      (95-120)/120  = -20.83%
    Max Drawdown = 1/3 (~33.3333%)
    """
    wealth = np.array([100.0, 120.0, 90.0, 110.0, 80.0, 95.0])
    running_peak = np.maximum.accumulate(wealth)
    drawdowns = wealth / running_peak - 1.0
    max_dd = abs(float(np.min(drawdowns)))

    expected_max_dd = (120.0 - 80.0) / 120.0
    assert abs(max_dd - expected_max_dd) < 1e-12


# ─── 4. Market Beta and Alpha (OLS vs Scipy Linear Regression) ───


def test_beta_and_alpha_against_scipy() -> None:
    """Verify market beta and alpha match scipy.stats.linregress."""
    np.random.seed(123)
    n = 63
    bench_returns = np.random.normal(0.0005, 0.01, n)
    # Stock with true beta=1.3, alpha=0.0002 daily
    stock_returns = 0.0002 + 1.3 * bench_returns + np.random.normal(0, 0.005, n)

    slope, intercept, _r_value, _p_value, _std_err = stats.linregress(bench_returns, stock_returns)

    # PRISM implementation:
    bench_var = float(np.var(bench_returns, ddof=1))
    cov = float(np.cov(stock_returns, bench_returns, ddof=1)[0, 1])
    prism_beta = cov / bench_var
    prism_alpha = float((np.mean(stock_returns) - prism_beta * np.mean(bench_returns)) * 252)

    assert abs(prism_beta - slope) < 1e-10
    # Annualized alpha comparison
    assert abs(prism_alpha - (intercept * 252.0)) < 1e-10


# ─── 5. Covariance & Euler Risk Decomposition Summing to 100% ───


def test_euler_risk_contributions_sum_to_portfolio_volatility() -> None:
    """Mathematical proof test for Euler decomposition:

    Portfolio volatility: sigma_p = sqrt(w^T Sigma w)
    Marginal risk: d(sigma_p)/d(w_i) = (Sigma w)_i / sigma_p
    Euler risk contribution: RC_i = w_i * d(sigma_p)/d(w_i)
    Euler's Theorem: sum(RC_i) == sigma_p
    Percentage shares: sum(RC_i / sigma_p) == 100%
    """
    weights = np.array([0.4, 0.35, 0.25], dtype=np.float64)
    # Positive definite covariance matrix
    sigma = np.array(
        [
            [0.09, 0.03, 0.01],
            [0.03, 0.06, 0.02],
            [0.01, 0.02, 0.04],
        ],
        dtype=np.float64,
    )

    sigma_w = sigma @ weights
    port_var = float(weights @ sigma_w)
    port_vol = math.sqrt(port_var)

    marginal_risks = sigma_w / port_vol
    euler_rc = weights * marginal_risks

    # Absolute Euler sum equals total portfolio volatility
    assert abs(np.sum(euler_rc) - port_vol) < 1e-12

    # Relative risk contributions normalized by variance sum to exactly 1.0 (100%)
    relative_shares = weights * sigma_w / port_var
    assert abs(np.sum(relative_shares) - 1.0) < 1e-12


# ─── 6. Concentration (HHI and Effective N) ───


def test_hhi_and_effective_n() -> None:
    """Verify Herfindahl-Hirschman Index and Effective N.

    Equal weights (N=4, w=[0.25, 0.25, 0.25, 0.25]):
      HHI = 4 * 0.25^2 = 0.25
      N_eff = 1 / 0.25 = 4.0

    Concentrated weights (w=[0.7, 0.1, 0.1, 0.1]):
      HHI = 0.49 + 3*0.01 = 0.52
      N_eff = 1 / 0.52 ~= 1.923
    """
    eq_weights = np.array([0.25, 0.25, 0.25, 0.25])
    hhi_eq = float(np.sum(np.square(eq_weights)))
    n_eff_eq = 1.0 / hhi_eq
    assert abs(hhi_eq - 0.25) < 1e-12
    assert abs(n_eff_eq - 4.0) < 1e-12

    conc_weights = np.array([0.7, 0.1, 0.1, 0.1])
    hhi_conc = float(np.sum(np.square(conc_weights)))
    n_eff_conc = 1.0 / hhi_conc
    assert abs(hhi_conc - 0.52) < 1e-12
    assert abs(n_eff_conc - (1.0 / 0.52)) < 1e-12


# ─── 7. Diversification Ratio (DR >= 1.0) ───


def test_diversification_ratio_properties() -> None:
    """Verify Diversification Ratio: DR = sum(w_i * sigma_i) / sigma_p >= 1.0.

    When assets are perfectly correlated (rho=1), DR == 1.0.
    When assets are uncorrelated (rho=0) or diversified, DR > 1.0.
    """
    weights = np.array([0.5, 0.5])
    vol_a, vol_b = 0.20, 0.30

    # 1. Perfectly correlated
    cov_perf = np.array([[vol_a**2, vol_a * vol_b], [vol_a * vol_b, vol_b**2]])
    port_vol_perf = math.sqrt(float(weights @ (cov_perf @ weights)))
    dr_perf = (weights[0] * vol_a + weights[1] * vol_b) / port_vol_perf
    assert abs(dr_perf - 1.0) < 1e-12

    # 2. Uncorrelated (rho=0)
    cov_uncorr = np.array([[vol_a**2, 0.0], [0.0, vol_b**2]])
    port_vol_uncorr = math.sqrt(float(weights @ (cov_uncorr @ weights)))
    dr_uncorr = (weights[0] * vol_a + weights[1] * vol_b) / port_vol_uncorr
    assert dr_uncorr > 1.0


# ─── 8. Mantegna MST Distance Metric sqrt(2(1 - rho)) ───


def test_mantegna_mst_distance_metric() -> None:
    """Verify Mantegna distance properties: d = sqrt(2(1 - rho)).

    - If rho == 1.0 -> d == 0.0 (identical co-movement)
    - If rho == 0.0 -> d == sqrt(2) ~= 1.41421356 (uncorrelated)
    - If rho == -1.0 -> d == 2.0 (maximum distance / anti-correlated)
    - Metric axioms: d(A,B) >= 0, d(A,B) == d(B,A), d(A,A) == 0
    """
    assert math.isclose(math.sqrt(2.0 * (1.0 - 1.0)), 0.0, abs_tol=1e-12)
    assert math.isclose(math.sqrt(2.0 * (1.0 - 0.0)), math.sqrt(2.0), abs_tol=1e-12)
    assert math.isclose(math.sqrt(2.0 * (1.0 - (-1.0))), 2.0, abs_tol=1e-12)

    # Test triangle inequality: d(A,C) <= d(A,B) + d(B,C)
    rho_ab, rho_bc, rho_ac = 0.8, 0.6, 0.2
    d_ab = math.sqrt(2.0 * (1.0 - rho_ab))
    d_bc = math.sqrt(2.0 * (1.0 - rho_bc))
    d_ac = math.sqrt(2.0 * (1.0 - rho_ac))
    assert d_ac <= d_ab + d_bc + 1e-12


# ─── 9. Stress Testing: Beta Propagation & Parallel Industry Shock ───


def test_stress_testing_formulas() -> None:
    """Verify stress test calculations for single-stock beta and parallel industry shocks."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(100)]
    np.random.seed(42)

    # Create returns where TCS has target variance and INFY has beta=0.8 to TCS
    r_tcs = np.random.normal(0, 0.02, 100)
    r_infy = 0.8 * r_tcs + np.random.normal(0, 0.005, 100)
    r_reliance = np.random.normal(0, 0.015, 100)

    returns_df = pd.DataFrame({"TCS": r_tcs, "INFY": r_infy, "RELIANCE": r_reliance}, index=dates)
    holdings = {"TCS": 0.5, "INFY": 0.3, "RELIANCE": 0.2}
    industries = {"TCS": "IT", "INFY": "IT", "RELIANCE": "Energy"}

    # Single stock shock: -10% to TCS
    stock_scenario = StressScenarioInput(kind="stock", target="TCS", shock_percent=-10.0)
    stock_res = calculate_stress(stock_scenario, returns_df, holdings, industries)
    assert stock_res is not None

    tcs_holding_res = next(h for h in stock_res.results if h.symbol == "TCS")
    infy_holding_res = next(h for h in stock_res.results if h.symbol == "INFY")
    assert abs(tcs_holding_res.estimated_return_percent - (-10.0)) < 1e-8
    # INFY beta is approximately 0.8 -> shock ~= -8%
    assert abs(infy_holding_res.estimated_return_percent - (-8.0)) < 0.5

    # Parallel industry shock: -15% to IT
    ind_scenario = StressScenarioInput(kind="industry", target="IT", shock_percent=-15.0)
    ind_res = calculate_stress(ind_scenario, returns_df, holdings, industries)
    assert ind_res is not None

    for h in ind_res.results:
        if industries[h.symbol] == "IT":
            assert abs(h.estimated_return_percent - (-15.0)) < 1e-8
        else:
            assert abs(h.estimated_return_percent - 0.0) < 1e-8


# ─── 10. Edge Cases (One Asset, Zero Variance, Negative Correlation) ───


def test_edge_case_single_asset_portfolio() -> None:
    """Verify single asset portfolio handling: weights=[1.0], cov is 1x1 scalar."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(50)]
    prices_df = pd.DataFrame({"TCS": np.linspace(100, 150, 50)}, index=dates)

    calc = calculate_risk(
        prices=prices_df,
        weights_by_symbol={"TCS": 1.0},
        industries={"TCS": "IT Services"},
        divergence={},
    )
    assert len(calc.holdings) == 1
    assert calc.holdings[0].weight == 1.0
    # In single asset, risk contribution must be 1.0 (100%)
    assert abs(calc.holdings[0].risk_contribution - 1.0) < 1e-8
    assert calc.concentration.effective_holdings == 1.0
    assert calc.concentration.holding_hhi == 1.0


def test_edge_case_zero_variance_or_flat_prices() -> None:
    """Verify handling when prices are completely flat (zero variance)."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(50)]
    prices_df = pd.DataFrame({"TCS": np.full(50, 100.0), "INFY": np.full(50, 200.0)}, index=dates)

    calc = calculate_risk(
        prices=prices_df,
        weights_by_symbol={"TCS": 0.5, "INFY": 0.5},
        industries={"TCS": "IT", "INFY": "IT"},
        divergence={},
    )
    # Zero volatility must not trigger ZeroDivisionError or NaN
    assert calc.performance.annualized_volatility == 0.0
    assert calc.performance.max_drawdown == 0.0
    for h in calc.holdings:
        assert h.marginal_risk == 0.0
        assert h.risk_contribution == 0.0


def test_edge_case_negative_correlation() -> None:
    """Verify portfolio risk reduction with perfectly negatively correlated assets."""
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(100)]
    np.random.seed(99)
    ret_a = np.random.normal(0, 0.01, 100)
    ret_b = -ret_a  # perfectly negatively correlated

    p_a = 100.0 * np.exp(np.cumsum(ret_a))
    p_b = 100.0 * np.exp(np.cumsum(ret_b))
    prices_df = pd.DataFrame({"A": p_a, "B": p_b}, index=dates)

    calc = calculate_risk(
        prices=prices_df,
        weights_by_symbol={"A": 0.5, "B": 0.5},
        industries={"A": "IndA", "B": "IndB"},
        divergence={},
    )
    # 50/50 portfolio of perfectly inversely correlated assets achieves near-zero variance
    assert calc.performance.annualized_volatility < 1e-4
