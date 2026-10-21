"""Versioned stock metrics and cross-sectional percentile risk scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

ANNUAL_SESSIONS = 252
METHODOLOGY_VERSION = "nifty200-risk-percentile-v1"
WINDOWS = {"volatility_1m": 21, "volatility_3m": 63, "volatility_6m": 126, "volatility_1y": 252}
MINIMUM_RETURNS = {
    "volatility_1m": 15,
    "volatility_3m": 45,
    "volatility_6m": 90,
    "volatility_1y": 180,
}
CORE_MINIMUM_RETURNS = 180
BETA_MINIMUM_COMMON_RETURNS = 60
ATV_MINIMUM_OBSERVATIONS = 15
FACTOR_WEIGHTS = {
    "volatility": 0.30,
    "downside": 0.25,
    "drawdown": 0.20,
    "beta": 0.15,
    "instability": 0.10,
}


@dataclass(slots=True)
class MetricValues:
    symbol: str
    metric_date: date | None
    volatility_1m: float | None = None
    volatility_3m: float | None = None
    volatility_6m: float | None = None
    volatility_1y: float | None = None
    downside_volatility: float | None = None
    max_drawdown: float | None = None
    beta_nifty50: float | None = None
    average_traded_value_20d: float | None = None
    instability: float | None = None
    observations_used: int = 0
    missing_reasons: dict[str, str] = field(default_factory=dict)
    factor_scores: dict[str, float] = field(default_factory=dict)
    score: float | None = None

    def raw_factors(self) -> dict[str, float | None]:
        return {
            "volatility": self.volatility_1y,
            "downside": self.downside_volatility,
            "drawdown": self.max_drawdown,
            "beta": abs(self.beta_nifty50) if self.beta_nifty50 is not None else None,
            "instability": self.instability,
        }


@dataclass(frozen=True, slots=True)
class Calibration:
    factor: str
    lower_value: float
    upper_value: float
    eligible_count: int
    lower_percentile: float = 0.10
    upper_percentile: float = 0.90


def _annualized_volatility(values: pd.Series) -> float:
    return float(values.std(ddof=1) * math.sqrt(ANNUAL_SESSIONS))


def calculate_metric_values(
    symbol: str,
    adjusted_close: pd.Series,
    benchmark_adjusted_close: pd.Series,
    raw_close: pd.Series,
    volume: pd.Series,
) -> MetricValues:
    """Calculate only from observed values; unavailable metrics remain ``None``."""
    prices = adjusted_close.dropna().astype(float).sort_index()
    result = MetricValues(
        symbol=symbol,
        metric_date=prices.index[-1] if len(prices) else None,
        observations_used=max(len(prices) - 1, 0),
    )
    if len(prices) < 2:
        result.missing_reasons["all_metrics"] = "insufficient_price_observations"
        return result

    returns = np.log(prices / prices.shift(1)).dropna()
    for field_name, window in WINDOWS.items():
        minimum = MINIMUM_RETURNS[field_name]
        selected = returns.iloc[-window:]
        if len(selected) < minimum:
            result.missing_reasons[field_name] = f"requires_{minimum}_returns"
        else:
            setattr(result, field_name, _annualized_volatility(selected))

    core = returns.iloc[-ANNUAL_SESSIONS:]
    core_prices = prices.iloc[-(ANNUAL_SESSIONS + 1) :]
    if len(core) < CORE_MINIMUM_RETURNS:
        result.missing_reasons["downside_volatility"] = f"requires_{CORE_MINIMUM_RETURNS}_returns"
        result.missing_reasons["max_drawdown"] = f"requires_{CORE_MINIMUM_RETURNS}_returns"
    else:
        downside = np.minimum(core.to_numpy(dtype=float), 0.0)
        result.downside_volatility = float(
            math.sqrt(float(np.mean(np.square(downside)))) * math.sqrt(ANNUAL_SESSIONS)
        )
        wealth = core_prices / float(core_prices.iloc[0])
        drawdowns = wealth / wealth.cummax() - 1.0
        result.max_drawdown = float(abs(drawdowns.min()))

    benchmark = benchmark_adjusted_close.dropna().astype(float).sort_index()
    benchmark_returns = np.log(benchmark / benchmark.shift(1)).dropna()
    paired = pd.concat(
        [returns.rename("asset"), benchmark_returns.rename("benchmark")], axis=1, join="inner"
    ).dropna()
    paired = paired.iloc[-ANNUAL_SESSIONS:]
    if len(paired) < BETA_MINIMUM_COMMON_RETURNS:
        result.missing_reasons["beta_nifty50"] = (
            f"requires_{BETA_MINIMUM_COMMON_RETURNS}_common_returns"
        )
    else:
        benchmark_variance = float(paired["benchmark"].var(ddof=1))
        if benchmark_variance <= 0:
            result.missing_reasons["beta_nifty50"] = "zero_benchmark_variance"
        else:
            covariance = float(paired["asset"].cov(paired["benchmark"]))
            result.beta_nifty50 = covariance / benchmark_variance

    traded = pd.concat(
        [raw_close.rename("close"), volume.rename("volume")], axis=1, join="inner"
    ).dropna()
    traded = traded[traded["volume"] >= 0].iloc[-20:]
    if len(traded) < ATV_MINIMUM_OBSERVATIONS:
        result.missing_reasons["average_traded_value_20d"] = (
            f"requires_{ATV_MINIMUM_OBSERVATIONS}_observations"
        )
    else:
        result.average_traded_value_20d = float(
            (traded["close"].astype(float) * traded["volume"].astype(float)).mean()
        )

    if result.volatility_1m is None or result.volatility_1y is None:
        result.missing_reasons["factor_instability"] = "requires_1m_and_1y_volatility"
    elif result.volatility_1y == 0:
        result.missing_reasons["factor_instability"] = "zero_1y_volatility"
    else:
        result.instability = result.volatility_1m / result.volatility_1y
    return result


def calibrate_and_score(metrics: list[MetricValues]) -> dict[str, Calibration]:
    """Mutate metric objects with deterministic P10/P90 normalized factor scores."""
    calibrations: dict[str, Calibration] = {}
    for factor in FACTOR_WEIGHTS:
        observed = sorted(
            value
            for metric in metrics
            if (value := metric.raw_factors()[factor]) is not None and math.isfinite(value)
        )
        if not observed:
            continue
        lower = float(np.quantile(observed, 0.10, method="linear"))
        upper = float(np.quantile(observed, 0.90, method="linear"))
        calibrations[factor] = Calibration(factor, lower, upper, len(observed))

    for metric in metrics:
        raw = metric.raw_factors()
        for factor in FACTOR_WEIGHTS:
            value = raw[factor]
            calibration = calibrations.get(factor)
            if value is None or calibration is None:
                metric.missing_reasons[f"factor_{factor}"] = "cross_section_or_value_unavailable"
                continue
            if calibration.upper_value == calibration.lower_value:
                metric.missing_reasons[f"factor_{factor}"] = "zero_cross_sectional_range"
                continue
            normalized = (
                100.0
                * (value - calibration.lower_value)
                / (calibration.upper_value - calibration.lower_value)
            )
            metric.factor_scores[factor] = float(np.clip(normalized, 0.0, 100.0))
        if set(metric.factor_scores) == set(FACTOR_WEIGHTS):
            metric.score = sum(
                metric.factor_scores[factor] * weight for factor, weight in FACTOR_WEIGHTS.items()
            )
        else:
            metric.missing_reasons["score"] = "one_or_more_factors_unavailable"
    return calibrations
