"""Point-in-time benchmark residual return panel construction for the residual MST variant."""

from datetime import date
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.inputs import MstInputs
from backend.app.db.models import BenchmarkDefinition, BenchmarkSeries


def extract_benchmark_returns(
    session: Session | None,
    raw_returns: pd.DataFrame,
    trade_dates: list[date],
    benchmark_name: str = "NIFTY 200",
) -> pd.Series:
    """Extract point-in-time benchmark log returns.

    Falls back to equal-weighted universe return if benchmark is unavailable.
    """
    bench_returns: pd.Series | None = None

    if session is not None and len(trade_dates) > 1:
        try:
            bench_id = session.scalar(
                select(BenchmarkDefinition.id).where(BenchmarkDefinition.name == benchmark_name)
            )
            if bench_id is not None:
                rows = session.scalars(
                    select(BenchmarkSeries)
                    .where(
                        BenchmarkSeries.benchmark_id == bench_id,
                        BenchmarkSeries.trade_date.in_(trade_dates),
                    )
                    .order_by(BenchmarkSeries.trade_date)
                ).all()
                if len(rows) >= len(trade_dates) * 0.8:
                    prices = pd.Series(
                        {row.trade_date: float(row.close) for row in rows},
                        name="benchmark",
                    ).sort_index()
                    log_rets = np.log(prices / prices.shift(1)).dropna()
                    bench_returns = log_rets.reindex(raw_returns.index)
        except Exception:
            bench_returns = None

    if bench_returns is None or bench_returns.empty or bench_returns.isna().all():
        # Fallback to equal-weighted universe market return point-in-time
        bench_returns = raw_returns.mean(axis=1, skipna=True)
        bench_returns.name = "market_proxy"

    return bench_returns


def compute_ols_residuals(
    stock_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    min_observations: int = 30,
) -> tuple[np.ndarray, float, float, float]:
    """Compute OLS market model residuals: r_i,t = alpha_i + beta_i * r_m,t + eps_i,t.

    Returns:
        (residuals_array, alpha, beta, correlation_with_benchmark)
    """
    valid = np.isfinite(stock_returns) & np.isfinite(benchmark_returns)
    n_obs = int(valid.sum())
    residuals = np.full_like(stock_returns, np.nan, dtype=float)

    if n_obs < min_observations:
        return residuals, 0.0, 0.0, 0.0

    y = stock_returns[valid]
    x = benchmark_returns[valid]

    var_x = float(np.var(x, ddof=1))
    if var_x <= 1e-15:
        # Zero variance benchmark; residuals are demeaned returns
        mean_y = float(np.mean(y))
        residuals[valid] = y - mean_y
        return residuals, mean_y, 0.0, 0.0

    cov_xy = float(np.cov(x, y, ddof=1)[0, 1])
    beta = cov_xy / var_x
    alpha = float(np.mean(y)) - beta * float(np.mean(x))

    res_valid = y - (alpha + beta * x)
    residuals[valid] = res_valid

    # Verify correlation with benchmark is near zero
    std_res = float(np.std(res_valid, ddof=1))
    std_x = float(np.std(x, ddof=1))
    if std_res > 1e-12 and std_x > 1e-12:
        corr_with_bench = float(np.corrcoef(res_valid, x)[0, 1])
    else:
        corr_with_bench = 0.0

    return residuals, alpha, beta, corr_with_bench


def build_residual_inputs(
    raw_inputs: MstInputs,
    session: Session | None = None,
    benchmark_name: str = "NIFTY 200",
) -> tuple[MstInputs, dict[str, Any]]:
    """Build a residual MstInputs panel where the market benchmark return has been removed."""
    closes = raw_inputs.adjusted_closes
    symbols = list(closes.columns)
    trade_dates = list(closes.index)

    # Compute raw log returns
    raw_returns = np.log(closes / closes.shift(1)).iloc[1:]

    # Extract benchmark returns
    bench_returns = extract_benchmark_returns(
        session, raw_returns, trade_dates, benchmark_name=benchmark_name
    )

    residual_returns_df = pd.DataFrame(index=raw_returns.index, columns=symbols, dtype=float)
    stats: dict[str, dict[str, float]] = {}

    bm_vals = bench_returns.to_numpy(dtype=float)

    for sym in symbols:
        stk_vals = raw_returns[sym].to_numpy(dtype=float)
        res, alpha, beta, corr = compute_ols_residuals(stk_vals, bm_vals)
        residual_returns_df[sym] = res
        stats[sym] = {
            "alpha": round(alpha, 6),
            "beta": round(beta, 6),
            "residual_corr_with_benchmark": round(corr, 6),
        }

    # Reconstruct cumulative synthetic residual prices: P_t = P_0 * exp(cumsum(eps))
    # Starting base price is set to 100.0 for all stocks
    synthetic_closes = pd.DataFrame(index=closes.index, columns=symbols, dtype=float)
    synthetic_closes.iloc[0] = 100.0

    for i in range(len(residual_returns_df)):
        prev_prices = synthetic_closes.iloc[i].to_numpy(dtype=float)
        eps_step = residual_returns_df.iloc[i].to_numpy(dtype=float)
        new_prices = np.where(
            np.isfinite(prev_prices) & np.isfinite(eps_step),
            prev_prices * np.exp(eps_step),
            np.nan,
        )
        synthetic_closes.iloc[i + 1] = new_prices

    residual_inputs = MstInputs(
        window_end=raw_inputs.window_end,
        data_cutoff=raw_inputs.data_cutoff,
        adjusted_closes=synthetic_closes,
        adjustment_versions=raw_inputs.adjustment_versions,
        adjustment_times=raw_inputs.adjustment_times,
        security_ids=raw_inputs.security_ids,
        industries=raw_inputs.industries,
        membership_sources=raw_inputs.membership_sources,
        exclusions=raw_inputs.exclusions,
        formula_version=raw_inputs.formula_version,
    )

    summary_metadata = {
        "variant": "residual",
        "benchmark": benchmark_name,
        "total_symbols_residualized": len(symbols),
        "mean_beta": round(float(np.mean([s["beta"] for s in stats.values()])), 4),
        "max_abs_bench_correlation": round(
            float(np.max([abs(s["residual_corr_with_benchmark"]) for s in stats.values()])),
            8,
        ),
    }

    return residual_inputs, summary_metadata
