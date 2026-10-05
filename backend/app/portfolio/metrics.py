"""Core portfolio risk metrics: volatility, Euler decomposition, beta, drawdown, VaR/ES."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


@dataclass
class HoldingRiskContribution:
    symbol: str
    weight: float
    asset_volatility: float
    marginal_contribution: float
    percent_contribution: float
    beta: float | None = None
    notes: str | None = None


@dataclass
class PortfolioMetrics:
    portfolio_volatility: float
    portfolio_variance: float
    portfolio_beta: float | None
    max_drawdown: float
    var_historical_95: float | None
    var_parametric_95: float | None
    es_historical_95: float | None
    es_parametric_95: float | None
    concentration_metrics: dict[str, Any]
    drawdown_series: list[dict[str, Any]]
    contributions: list[HoldingRiskContribution]
    warnings: list[str] = field(default_factory=list)


def calculate_portfolio_metrics(
    symbols: list[str],
    weights: list[float],
    cov_matrix_annual: np.ndarray,
    returns_df: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    industries: dict[str, str | None] | None = None,
    mst_clusters: dict[str, str] | None = None,
    annualisation_factor: float = 252.0,
) -> PortfolioMetrics:
    """Calculate core portfolio risk metrics per PRISM SRS FR-R1 to FR-R7.

    Symbols list and cov_matrix_annual include all assets (including CASH if present).
    Euler decomposition guarantees:
    - sum(w_i * MRC_i) == portfolio_volatility
    - sum(PRC_i) == 1.0 (or 0.0 if all-cash portfolio)
    """
    warnings: list[str] = []
    w = np.array(weights, dtype=np.float64)
    n = len(symbols)

    if n == 0 or len(w) == 0:
        return PortfolioMetrics(
            portfolio_volatility=0.0,
            portfolio_variance=0.0,
            portfolio_beta=None,
            max_drawdown=0.0,
            var_historical_95=None,
            var_parametric_95=None,
            es_historical_95=None,
            es_parametric_95=None,
            concentration_metrics={},
            drawdown_series=[],
            contributions=[],
            warnings=["Empty portfolio provided."],
        )

    # Portfolio variance and volatility
    sigma_w = np.dot(cov_matrix_annual, w)
    port_variance = float(np.dot(w, sigma_w))
    port_volatility = math.sqrt(max(port_variance, 0.0))

    # Asset volatilities
    diag_vars = np.diag(cov_matrix_annual)
    asset_vols = [math.sqrt(max(float(v), 0.0)) for v in diag_vars]

    # Euler decomposition
    contributions: list[HoldingRiskContribution] = []
    for i in range(n):
        sym = symbols[i]
        wt = float(w[i])
        vol_i = asset_vols[i]

        if port_volatility > 1e-12:
            mrc_i = float(sigma_w[i] / port_volatility)
            prc_i = float(wt * sigma_w[i] / port_variance)
        else:
            mrc_i = 0.0
            prc_i = 0.0

        contributions.append(
            HoldingRiskContribution(
                symbol=sym,
                weight=wt,
                asset_volatility=vol_i,
                marginal_contribution=mrc_i,
                percent_contribution=prc_i,
                beta=None,
                notes="Euler risk contribution calculated with point-in-time covariance.",
            )
        )

    # Beta vs Benchmark (portfolio and holdings)
    port_beta: float | None = None
    has_benchmark = (
        benchmark_returns is not None and len(benchmark_returns) > 1 and not returns_df.empty
    )

    if has_benchmark and benchmark_returns is not None:
        # Align returns on common dates
        common_idx = returns_df.index.intersection(benchmark_returns.index)
        if len(common_idx) > 5:
            bench_aligned = benchmark_returns.loc[common_idx]
            var_bench = float(bench_aligned.var(ddof=1))
            if var_bench > 1e-12:
                # Per-holding beta
                betas: list[float | None] = []
                for i in range(n):
                    sym = symbols[i]
                    if sym in returns_df.columns:
                        ret_i = returns_df.loc[common_idx, sym]
                        cov_i_m = float(np.cov(ret_i, bench_aligned, ddof=1)[0, 1])
                        beta_i = cov_i_m / var_bench
                        betas.append(beta_i)
                        contributions[i].beta = beta_i
                    else:
                        # Cash or unmapped asset has 0 correlation with benchmark
                        betas.append(0.0)
                        contributions[i].beta = 0.0

                # Portfolio beta is weighted sum of asset betas
                port_beta = float(sum(w[i] * (betas[i] or 0.0) for i in range(n)))
            else:
                warnings.append("Benchmark variance is near zero; beta calculation skipped.")
        else:
            warnings.append("Insufficient overlapping dates with benchmark for beta estimation.")

    # Historical returns, Drawdown and Max Drawdown
    drawdown_series: list[dict[str, Any]] = []
    max_dd = 0.0
    var_hist_95: float | None = None
    es_hist_95: float | None = None
    var_param_95: float | None = None
    es_param_95: float | None = None

    if not returns_df.empty and len(returns_df) > 0:
        # Build portfolio historical return series
        # Note: columns in returns_df match risky symbols
        port_daily_ret = np.zeros(len(returns_df), dtype=np.float64)
        for i in range(n):
            sym = symbols[i]
            if sym in returns_df.columns:
                port_daily_ret += w[i] * returns_df[sym].values

        # Cumulative wealth index W_t
        wealth = np.exp(np.cumsum(port_daily_ret))
        hwm = np.maximum.accumulate(wealth)
        dd = (wealth - hwm) / hwm
        max_dd = float(abs(np.min(dd))) if len(dd) > 0 else 0.0

        for tdate, dd_val, ret_val in zip(returns_df.index, dd, port_daily_ret, strict=False):
            drawdown_series.append(
                {
                    "date": tdate.isoformat() if hasattr(tdate, "isoformat") else str(tdate),
                    "drawdown": round(float(dd_val), 6),
                    "portfolio_return": round(float(ret_val), 6),
                }
            )

        # Historical VaR & ES (1-day, 95%)
        # Loss L = -r
        losses = -port_daily_ret
        if len(losses) >= 10:
            var_hist_95 = float(np.percentile(losses, 95.0))
            tail_losses = losses[losses >= var_hist_95]
            es_hist_95 = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_hist_95

    # Parametric VaR & ES (1-day, 95% Normal assumption)
    daily_vol = port_volatility / math.sqrt(annualisation_factor)
    z_95 = 1.6448536269514722
    phi_z = 0.10313564037803026  # Standard normal PDF at z_95: exp(-z^2/2) / sqrt(2*pi)
    var_param_95 = float(z_95 * daily_vol)
    es_param_95 = float(daily_vol * (phi_z / 0.05))

    # Concentration Metrics
    # 1. Holding HHI (Herfindahl-Hirschman Index) & Effective N
    holding_hhi = float(sum(wt**2 for wt in w))
    effective_n = float(1.0 / holding_hhi) if holding_hhi > 1e-12 else 0.0

    # 2. Industry Concentration
    industry_weights: dict[str, float] = {}
    for i in range(n):
        sym = symbols[i]
        ind = (
            "Cash"
            if sym == "CASH"
            else (industries.get(sym) or "Unclassified")
            if industries
            else "Unclassified"
        )
        industry_weights[ind] = industry_weights.get(ind, 0.0) + float(w[i])

    industry_hhi = float(sum(wt**2 for wt in industry_weights.values()))

    # 3. MST Cluster Concentration
    cluster_metrics: dict[str, Any]
    if mst_clusters and any(sym in mst_clusters for sym in symbols):
        cluster_weights: dict[str, float] = {}
        for i in range(n):
            sym = symbols[i]
            c_id = mst_clusters.get(sym, "Unclustered" if sym != "CASH" else "Cash")
            cluster_weights[c_id] = cluster_weights.get(c_id, 0.0) + float(w[i])
        cluster_hhi = float(sum(wt**2 for wt in cluster_weights.values()))
        cluster_metrics = {
            "status": "available",
            "cluster_weights": {k: round(v, 6) for k, v in cluster_weights.items()},
            "cluster_hhi": round(cluster_hhi, 6),
            "effective_clusters": round(1.0 / cluster_hhi, 2) if cluster_hhi > 0 else 0.0,
        }
    else:
        cluster_metrics = {
            "status": "unavailable",
            "reason": "No approved Layer 2 MST clusters found for active holdings",
        }

    concentration_metrics = {
        "holding_hhi": round(holding_hhi, 6),
        "effective_n": round(effective_n, 2),
        "top_holding_weight": round(float(max(w)), 6),
        "industry_weights": {k: round(v, 6) for k, v in industry_weights.items()},
        "industry_hhi": round(industry_hhi, 6),
        "mst_clusters": cluster_metrics,
    }

    return PortfolioMetrics(
        portfolio_volatility=round(port_volatility, 8),
        portfolio_variance=round(port_variance, 10),
        portfolio_beta=round(port_beta, 6) if port_beta is not None else None,
        max_drawdown=round(max_dd, 6),
        var_historical_95=round(var_hist_95, 6) if var_hist_95 is not None else None,
        var_parametric_95=round(var_param_95, 6) if var_param_95 is not None else None,
        es_historical_95=round(es_hist_95, 6) if es_hist_95 is not None else None,
        es_parametric_95=round(es_param_95, 6) if es_param_95 is not None else None,
        concentration_metrics=concentration_metrics,
        drawdown_series=drawdown_series,
        contributions=contributions,
        warnings=warnings,
    )
