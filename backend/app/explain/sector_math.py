"""Pure read-only calculations used by Step E3 explanations."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class RegressionDiagnostics:
    expected_return: float
    residual: float
    r_squared: float
    observations: int


def peer_median_daily_returns(
    prices: pd.DataFrame,
    peer_symbols: list[str],
    minimum_peers: int,
) -> pd.Series:
    """Reproduce Layer 1's contemporaneous peer-median daily log-return series."""
    if not peer_symbols:
        return pd.Series(index=prices.index, dtype="float64")
    returns = np.log(prices[peer_symbols].astype("float64")).diff()
    median = returns.median(axis=1, skipna=True)
    return median.where(returns.notna().sum(axis=1) >= minimum_peers)


def period_return_percent(returns: pd.Series, horizon: int) -> float | None:
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    values = returns.iloc[-horizon:].to_numpy(dtype=float)
    if len(values) != horizon or not np.isfinite(values).all():
        return None
    return 100.0 * (exp(float(values.sum())) - 1.0)


def constituent_period_returns(
    prices: pd.DataFrame, symbols: list[str], horizon: int
) -> dict[str, float]:
    returns = np.log(prices[symbols].astype("float64")).diff()
    output: dict[str, float] = {}
    for symbol in symbols:
        value = period_return_percent(returns[symbol], horizon)
        if value is not None:
            output[symbol] = value
    return output


def trend_label(return_percent: float, flat_threshold_percent: float) -> str:
    if flat_threshold_percent < 0:
        raise ValueError("flat threshold must not be negative")
    if return_percent > flat_threshold_percent:
        return "up"
    if return_percent < -flat_threshold_percent:
        return "down"
    return "flat"


def weak_absolute_percentile(target: float, values: list[float]) -> float | None:
    finite = sorted(abs(value) for value in values if np.isfinite(value))
    if not finite:
        return None
    return 100.0 * sum(value <= abs(target) for value in finite) / len(finite)


def persistence_count(values: list[float], threshold: float, window: int) -> tuple[int, int]:
    if threshold < 0 or window <= 0:
        raise ValueError("threshold and window must be positive")
    finite = [value for value in values if np.isfinite(value)][-window:]
    return sum(abs(value) > threshold for value in finite), len(finite)


def regression_diagnostics(
    target_returns: pd.Series,
    peer_returns: pd.Series,
    *,
    alpha: float,
    beta: float,
    estimation_window: int,
) -> RegressionDiagnostics:
    if len(target_returns) != len(peer_returns):
        raise ValueError("target and peer return series must be aligned")
    current_target = float(target_returns.iloc[-1])
    current_peer = float(peer_returns.iloc[-1])
    if not np.isfinite(current_target) or not np.isfinite(current_peer):
        raise ValueError("current returns are unavailable")
    history_target = target_returns.iloc[-(estimation_window + 1) : -1].to_numpy(dtype=float)
    history_peer = peer_returns.iloc[-(estimation_window + 1) : -1].to_numpy(dtype=float)
    paired = np.isfinite(history_target) & np.isfinite(history_peer)
    observed = history_target[paired]
    fitted = alpha + beta * history_peer[paired]
    if len(observed) < 2:
        raise ValueError("insufficient paired observations for R-squared")
    total = float(np.sum((observed - observed.mean()) ** 2))
    residual_sum = float(np.sum((observed - fitted) ** 2))
    r_squared = 0.0 if total <= 0 else 1.0 - residual_sum / total
    expected = alpha + beta * current_peer
    return RegressionDiagnostics(
        expected_return=expected,
        residual=current_target - expected,
        r_squared=r_squared,
        observations=int(paired.sum()),
    )


def contribution_share(
    component_points: float, component_weight: float, total_score: float
) -> float | None:
    if total_score <= 0:
        return None
    return 100.0 * component_points * component_weight / total_score


def rebased_chart_points(
    target_returns: pd.Series,
    peer_returns: pd.Series,
    *,
    max_points: int,
) -> list[dict[str, object]]:
    if max_points <= 0:
        raise ValueError("max_points must be positive")
    frame = pd.concat(
        [target_returns.rename("stock"), peer_returns.rename("sector")], axis=1
    ).dropna()
    stock_index = 100.0 * np.exp(frame["stock"].cumsum())
    sector_index = 100.0 * np.exp(frame["sector"].cumsum())
    points = [
        {
            "date": index.isoformat(),
            "stock": round(float(stock_index.loc[index]), 6),
            "sector": round(float(sector_index.loc[index]), 6),
            "residual": round(float(stock_index.loc[index] - sector_index.loc[index]), 6),
        }
        for index in frame.index
    ]
    if len(points) <= max_points:
        return points
    selected = np.linspace(0, len(points) - 1, max_points, dtype=int)
    return [points[int(index)] for index in sorted(set(selected))]
