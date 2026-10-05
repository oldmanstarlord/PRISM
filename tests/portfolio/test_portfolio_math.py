"""Hand-calculated mathematical proofs and core metric unit tests for Step 3."""

import math
from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from backend.app.portfolio.metrics import calculate_portfolio_metrics
from backend.app.portfolio.parser import (
    HoldingInput,
    normalize_portfolio_holdings,
    parse_csv_holdings,
)


def test_hand_calculated_worked_example_shrinkage_zero() -> None:
    """Verify exact hand-calculated test case:

    Weights: 50% Asset 1, 30% Asset 2, 20% Asset 3
    Vols: 20%, 30%, 25%
    Correlations: rho_12=0.6, rho_13=0.4, rho_23=0.5
    => Portfolio Volatility: 19.97% (0.1997498)
    => Risk Contributions: 43.6% / 39.5% / 16.9%
    """
    symbols = ["ASSET_1", "ASSET_2", "ASSET_3"]
    weights = [0.5, 0.3, 0.2]
    vols = [0.20, 0.30, 0.25]
    corr = np.array(
        [
            [1.0, 0.6, 0.4],
            [0.6, 1.0, 0.5],
            [0.4, 0.5, 1.0],
        ]
    )

    # Covariance Sigma_ij = rho_ij * sigma_i * sigma_j
    cov_annual = np.zeros((3, 3), dtype=np.float64)
    for i in range(3):
        for j in range(3):
            cov_annual[i, j] = corr[i, j] * vols[i] * vols[j]

    # Verify Sigma elements:
    # Sigma_11 = 0.0400, Sigma_22 = 0.0900, Sigma_33 = 0.0625
    # Sigma_12 = 0.6 * 0.2 * 0.3 = 0.0360
    # Sigma_13 = 0.4 * 0.2 * 0.25 = 0.0200
    # Sigma_23 = 0.5 * 0.3 * 0.25 = 0.0375
    assert pytest.approx(cov_annual[0, 0], abs=1e-6) == 0.0400
    assert pytest.approx(cov_annual[1, 1], abs=1e-6) == 0.0900
    assert pytest.approx(cov_annual[2, 2], abs=1e-6) == 0.0625
    assert pytest.approx(cov_annual[0, 1], abs=1e-6) == 0.0360
    assert pytest.approx(cov_annual[0, 2], abs=1e-6) == 0.0200
    assert pytest.approx(cov_annual[1, 2], abs=1e-6) == 0.0375

    # Run metrics calculation
    dummy_returns = pd.DataFrame(columns=symbols)
    metrics = calculate_portfolio_metrics(
        symbols=symbols,
        weights=weights,
        cov_matrix_annual=cov_annual,
        returns_df=dummy_returns,
        annualisation_factor=252.0,
    )

    # Portfolio Volatility sqrt(w' S w) = sqrt(0.0399) = 19.97498% => 19.97%
    assert pytest.approx(metrics.portfolio_volatility, abs=1e-4) == 0.1997
    assert pytest.approx(round(metrics.portfolio_volatility * 100, 2), abs=1e-2) == 19.97
    assert pytest.approx(metrics.portfolio_variance, abs=1e-6) == 0.0399

    # Marginal Risk Contributions: (Sigma w)_i / sigma_p
    # Sigma w = [0.0348, 0.0525, 0.03375]
    # MRC_1 = 0.0348 / 0.1997498 = 0.174218
    # MRC_2 = 0.0525 / 0.1997498 = 0.262829
    # MRC_3 = 0.03375 / 0.1997498 = 0.168961
    c1, c2, c3 = metrics.contributions
    assert c1.symbol == "ASSET_1"
    assert c2.symbol == "ASSET_2"
    assert c3.symbol == "ASSET_3"

    # Percentage Risk Contributions w_i * (Sigma w)_i / sigma_p^2:
    # PRC_1 = 0.5 * 0.0348 / 0.0399 = 0.0174 / 0.0399 = 43.609% => 43.6%
    # PRC_2 = 0.3 * 0.0525 / 0.0399 = 0.01575 / 0.0399 = 39.474% => 39.5%
    # PRC_3 = 0.2 * 0.03375 / 0.0399 = 0.00675 / 0.0399 = 16.917% => 16.9%
    assert pytest.approx(round(c1.percent_contribution * 100, 1), abs=0.1) == 43.6
    assert pytest.approx(round(c2.percent_contribution * 100, 1), abs=0.1) == 39.5
    assert pytest.approx(round(c3.percent_contribution * 100, 1), abs=0.1) == 16.9

    # Euler identity checks
    euler_sum = sum(
        w * c.marginal_contribution for w, c in zip(weights, metrics.contributions, strict=True)
    )
    assert pytest.approx(euler_sum, abs=1e-6) == metrics.portfolio_volatility

    total_prc = sum(c.percent_contribution for c in metrics.contributions)
    assert pytest.approx(total_prc, abs=1e-6) == 1.0


def test_weight_normalization_with_cash() -> None:
    """Verify weight normalization and explicit cash drag allocation."""
    mock_session = MagicMock()
    sec_id1 = uuid4()
    sec_id2 = uuid4()

    # Mock symbol resolution
    def execute_mock(stmt):
        return [("INFY", sec_id1), ("TCS", sec_id2)]

    mock_session.execute.side_effect = [
        [("INFY", sec_id1), ("TCS", sec_id2)],  # Alias query
        [],
        [],
    ]

    # Case 1: Weights < 1.0 (0.45 + 0.35 = 0.80) => residual 0.20 allocated to CASH
    inputs = [
        HoldingInput(symbol="INFY", weight=0.45),
        HoldingInput(symbol="TCS", weight=0.35),
    ]

    holdings, errors, warnings = normalize_portfolio_holdings(
        session=mock_session,
        inputs=inputs,
        as_of=date(2026, 10, 1),
    )

    assert not errors
    assert len(holdings) == 3
    cash_holding = next(h for h in holdings if h.symbol == "CASH")
    assert pytest.approx(float(cash_holding.weight), abs=1e-6) == 0.20
    assert any("residual 0.2000 allocated to CASH" in w for w in warnings)
    total_wt = sum(h.weight for h in holdings)
    assert pytest.approx(float(total_wt), abs=1e-6) == 1.0

    # Case 2: Weights > 1.0 (0.60 + 0.60 = 1.20) => scaled by 1/1.2 = 0.50 each
    mock_session.execute.side_effect = [
        [("INFY", sec_id1), ("TCS", sec_id2)],
        [],
        [],
    ]
    inputs_over = [
        HoldingInput(symbol="INFY", weight=0.60),
        HoldingInput(symbol="TCS", weight=0.60),
    ]
    holdings_over, errors_over, warnings_over = normalize_portfolio_holdings(
        session=mock_session,
        inputs=inputs_over,
        as_of=date(2026, 10, 1),
    )
    assert not errors_over
    assert len(holdings_over) == 2
    assert pytest.approx(float(holdings_over[0].weight), abs=1e-6) == 0.50
    assert pytest.approx(float(holdings_over[1].weight), abs=1e-6) == 0.50


def test_beta_on_constructed_series() -> None:
    """Verify beta calculation vs benchmark:

    If an asset has return r_i = 1.5 * r_bench, its beta must strictly equal 1.5.
    And a 50/50 portfolio with an asset of beta 1.5 and cash (beta 0) has portfolio beta 0.75.
    """
    dates = pd.date_range("2026-01-01", periods=100, freq="B")
    np.random.seed(42)
    bench_returns = pd.Series(np.random.normal(0.0005, 0.01, size=len(dates)), index=dates)

    # Asset 1: beta = 1.5
    asset1_returns = 1.5 * bench_returns + np.random.normal(0, 0.001, size=len(dates))

    returns_df = pd.DataFrame({"INFY": asset1_returns}, index=dates)
    cov_annual = np.array([[float(asset1_returns.var() * 252.0), 0.0], [0.0, 0.0]])

    symbols = ["INFY", "CASH"]
    weights = [0.5, 0.5]

    metrics = calculate_portfolio_metrics(
        symbols=symbols,
        weights=weights,
        cov_matrix_annual=cov_annual,
        returns_df=returns_df,
        benchmark_returns=bench_returns,
        annualisation_factor=252.0,
    )

    # Asset 1 beta should be approx 1.5
    asset1_c = next(c for c in metrics.contributions if c.symbol == "INFY")
    assert asset1_c.beta is not None
    assert pytest.approx(asset1_c.beta, abs=0.05) == 1.5

    # Cash beta is 0.0
    cash_c = next(c for c in metrics.contributions if c.symbol == "CASH")
    assert cash_c.beta == 0.0

    # Portfolio beta = 0.5 * 1.5 + 0.5 * 0.0 = 0.75
    assert metrics.portfolio_beta is not None
    assert pytest.approx(metrics.portfolio_beta, abs=0.05) == 0.75


def test_max_drawdown_on_toy_path() -> None:
    """Verify max drawdown on a toy path with known peak and trough.

    Path: Day 0 = 100, Day 1 = 120 (Peak), Day 2 = 90 (Trough: -25%), Day 3 = 105.
    Max Drawdown must equal 0.25 (25.0%).
    """
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    # Returns from prices [100 -> 120 -> 90 -> 105]
    # r_1 = ln(120 / 100) = ln(1.2)
    # r_2 = ln(90 / 120) = ln(0.75)
    # r_3 = ln(105 / 90) = ln(1.166667)
    r1 = math.log(1.2)
    r2 = math.log(0.75)
    r3 = math.log(105.0 / 90.0)

    returns_df = pd.DataFrame({"STOCK": [r1, r2, r3]}, index=dates)
    cov_dummy = np.array([[0.04]])

    metrics = calculate_portfolio_metrics(
        symbols=["STOCK"],
        weights=[1.0],
        cov_matrix_annual=cov_dummy,
        returns_df=returns_df,
        annualisation_factor=252.0,
    )

    # Max Drawdown = (90 - 120) / 120 = -0.25 => abs value 0.25
    assert pytest.approx(metrics.max_drawdown, abs=1e-4) == 0.25
    assert len(metrics.drawdown_series) == 3
    # On day 2, drawdown is -0.25
    assert pytest.approx(metrics.drawdown_series[1]["drawdown"], abs=1e-4) == -0.25


def test_csv_parser_and_row_error_reporting() -> None:
    """Verify CSV parser correctly identifies row-level errors."""
    csv_text = """symbol,quantity,weight
INFY,10,0.5
,20,0.2
TCS,-5,0.3
WIPRO,10,invalid
INFY,15,0.1
"""
    holdings, errors = parse_csv_holdings(csv_text)
    assert len(errors) == 4
    # Row 3: missing symbol
    err_blank = next(e for e in errors if e.row == 3)
    assert err_blank.field == "symbol"
    # Row 4: negative quantity
    err_neg = next(e for e in errors if e.row == 4)
    assert err_neg.field == "quantity"
    # Row 5: non-numeric weight
    err_non_num = next(e for e in errors if e.row == 5)
    assert err_non_num.field == "weight"
    # Row 6: duplicate symbol INFY
    err_dup = next(e for e in errors if e.row == 6)
    assert err_dup.symbol == "INFY"
    assert "Duplicate symbol" in err_dup.error
