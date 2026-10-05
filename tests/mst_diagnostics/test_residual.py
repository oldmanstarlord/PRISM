"""Tests for residual variant panel construction and OLS market factor removal."""

from datetime import UTC, date, datetime
from types import MappingProxyType
from uuid import uuid4

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from backend.app.correlation_mst.calculator import calculate_mst
from backend.app.correlation_mst.inputs import MstInputs
from backend.app.mst_diagnostics.residual import (
    build_residual_inputs,
    compute_ols_residuals,
)


def test_ols_residuals_removes_market_factor_completely() -> None:
    """Mathematical test: correlation of OLS residuals with the regressor must be zero."""
    rng = np.random.default_rng(42)
    n = 1000

    # Market returns series
    r_m = rng.normal(0.0005, 0.015, size=n)

    # 3 stocks with distinct alphas, betas, and idiosyncratic noises
    alphas = [0.0002, -0.0001, 0.0005]
    betas = [0.85, 1.25, -0.40]

    for a, b in zip(alphas, betas, strict=True):
        eps_true = rng.normal(0, 0.005, size=n)
        r_stock = a + b * r_m + eps_true

        residuals, est_alpha, est_beta, corr_with_bm = compute_ols_residuals(r_stock, r_m)

        # 1. Estimated parameters must be close to true parameters
        assert abs(est_beta - b) < 0.05
        assert abs(est_alpha - a) < 0.005

        # 2. Key requirement: correlation with benchmark is about zero (< 1e-12)
        assert abs(corr_with_bm) < 1e-12

        # 3. Direct verification of sample covariance with benchmark
        cov_res_bm = float(np.cov(residuals, r_m, ddof=1)[0, 1])
        assert abs(cov_res_bm) < 1e-14


def test_residual_inputs_panel_feeds_layer2_calculator() -> None:
    """Verify residual panel is valid MstInputs and executes through unchanged calculate_mst."""
    rng = np.random.default_rng(123)
    trade_dates = [date(2026, 1, 1) + pd.Timedelta(days=i) for i in range(130)]
    symbols = ["INFY", "TCS", "HDFCBANK", "ICICIBANK", "RELIANCE"]

    sec_ids = {sym: uuid4() for sym in symbols}
    industries = {
        "INFY": "Information Technology",
        "TCS": "Information Technology",
        "HDFCBANK": "Financial Services",
        "ICICIBANK": "Financial Services",
        "RELIANCE": "Oil Gas & Consumable Fuels",
    }
    sources = {sym: "NSE_INDEX" for sym in symbols}

    # Generate synthetic random walks for stock prices
    index = pd.Index(trade_dates, name="trade_date")
    closes = pd.DataFrame(index=index, columns=symbols, dtype=float)
    closes.iloc[0] = [1500.0, 3800.0, 1600.0, 1000.0, 2800.0]

    for t in range(1, len(trade_dates)):
        rets = rng.normal(0.0003, 0.012, size=len(symbols))
        closes.iloc[t] = closes.iloc[t - 1] * np.exp(rets)

    versions = pd.DataFrame("v1", index=index, columns=symbols)
    times = pd.DataFrame(datetime.now(UTC), index=index, columns=symbols)

    raw_inputs = MstInputs(
        window_end=trade_dates[-1],
        data_cutoff=datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC),
        adjusted_closes=closes,
        adjustment_versions=versions,
        adjustment_times=times,
        security_ids=MappingProxyType(sec_ids),
        industries=MappingProxyType(industries),
        membership_sources=MappingProxyType(sources),
        exclusions=(),
    )

    # Build residual inputs
    res_inputs, meta = build_residual_inputs(raw_inputs, session=None)
    assert meta["variant"] == "residual"
    assert meta["total_symbols_residualized"] == 5
    assert meta["max_abs_bench_correlation"] < 1e-10

    # Feed to unchanged Layer 2 calculator
    calc = calculate_mst(res_inputs)

    assert calc.is_connected is True
    assert calc.is_acyclic is True
    assert len(calc.nodes) == 5
    assert len(calc.edges) == 4  # N - 1 edges
    for e in calc.edges:
        assert 0.0 <= e.distance <= 2.0
        assert -1.0 <= e.correlation <= 1.0
