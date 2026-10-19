"""Purely mathematical implementation of the sector-divergence-v1 contract."""

from bisect import bisect_right
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from math import sqrt
from uuid import UUID

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from backend.app.sector_divergence.inputs import (
    FORMULA_VERSION,
    InputExclusion,
    SectorDivergenceInputs,
)

ESTIMATION_WINDOW = 60
MINIMUM_PAIRED_OBSERVATIONS = 45
MINIMUM_CONTEMPORANEOUS_PEERS = 4
HORIZONS = (1, 5, 20)
NUMERICAL_ZERO_TOLERANCE = 1e-15


@dataclass(frozen=True, slots=True)
class CalculationIssue:
    security_id: UUID
    symbol: str
    signal_date: date
    reason: str
    details: str
    horizon: int | None = None


@dataclass(frozen=True, slots=True)
class DivergenceScore:
    security_id: UUID
    symbol: str
    signal_date: date
    industry: str
    horizon: int
    residual_value: float
    divergence_value: float
    alpha: float
    beta: float
    residual_volatility: float
    industry_percentile: float
    interpretation: str
    lookback_start: date
    lookback_end: date
    observations_used: int
    data_cutoff: datetime
    membership_source: str
    adjustment_version: str
    implementation_version: str
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class SectorDivergenceCalculation:
    signal_date: date
    scores: tuple[DivergenceScore, ...]
    issues: tuple[CalculationIssue, ...]
    input_exclusions: tuple[InputExclusion, ...]
    implementation_version: str = FORMULA_VERSION


@dataclass(frozen=True, slots=True)
class _DailyEstimate:
    residual: float
    alpha: float
    beta: float
    residual_volatility: float
    observations_used: int
    lookback_start: date
    lookback_end: date


def _interpret(value: float) -> str:
    magnitude = abs(value)
    if magnitude < 1:
        return "normal"
    if magnitude < 2:
        return "moderate"
    if magnitude < 3:
        return "strong"
    return "extreme"


def _validate_inputs(inputs: SectorDivergenceInputs, computed_at: datetime) -> None:
    if computed_at.tzinfo is None or computed_at.utcoffset() is None:
        raise ValueError("computed_at must be timezone-aware")
    if inputs.formula_version != FORMULA_VERSION:
        raise ValueError(
            f"Unsupported input formula version {inputs.formula_version!r}; "
            f"expected {FORMULA_VERSION!r}"
        )
    if inputs.adjusted_closes.index.has_duplicates:
        raise ValueError("Adjusted-close panel contains duplicate trading dates")
    missing_columns = set(inputs.security_ids).difference(inputs.adjusted_closes.columns)
    if missing_columns:
        raise ValueError(f"Adjusted-close panel is missing symbols: {sorted(missing_columns)}")
    if inputs.signal_date not in inputs.adjusted_closes.index:
        raise ValueError(f"No adjusted-price row exists for signal date {inputs.signal_date}")
    if inputs.signal_date not in inputs.adjustment_versions.index:
        raise ValueError(f"No adjustment-version row exists for signal date {inputs.signal_date}")


def _calculate_daily_estimates(
    prices: pd.DataFrame,
    industries: dict[str, str],
    opens: pd.DataFrame | None = None,
) -> tuple[dict[tuple[str, int], _DailyEstimate], dict[tuple[str, int], str]]:
    close_vals = prices.astype("float64")
    if opens is not None and not opens.empty:
        open_vals = opens.reindex(index=prices.index, columns=prices.columns).astype("float64")
        valid_open = (open_vals > 0) & np.isfinite(open_vals) & (close_vals > 0) & np.isfinite(close_vals)
        intraday_returns = np.where(valid_open, np.log(close_vals / np.where(valid_open, open_vals, 1.0)), np.nan)
        close_diff_returns = np.log(close_vals).diff().to_numpy()
        combined_returns = np.where(valid_open, intraday_returns, close_diff_returns)
        returns = pd.DataFrame(combined_returns, index=prices.index, columns=prices.columns)
    else:
        returns = np.log(close_vals).diff()
    dates = list(prices.index)
    estimates: dict[tuple[str, int], _DailyEstimate] = {}
    failures: dict[tuple[str, int], str] = {}

    industry_symbols: dict[str, list[str]] = {}
    for symbol, industry in industries.items():
        industry_symbols.setdefault(industry, []).append(symbol)
    for symbols in industry_symbols.values():
        symbols.sort()

    for symbol in sorted(industries):
        industry = industries[symbol]
        peers = [candidate for candidate in industry_symbols[industry] if candidate != symbol]
        peer_returns = returns[peers]
        benchmark = peer_returns.median(axis=1, skipna=True)
        benchmark = benchmark.where(
            peer_returns.notna().sum(axis=1) >= MINIMUM_CONTEMPORANEOUS_PEERS
        )
        target_returns = returns[symbol]

        for position in range(len(dates)):
            if position == 0:
                continue
            current_target = target_returns.iloc[position]
            current_benchmark = benchmark.iloc[position]
            if not np.isfinite(current_target):
                failures[(symbol, position)] = "missing_current_return"
                continue
            if not np.isfinite(current_benchmark):
                failures[(symbol, position)] = "insufficient_contemporaneous_peers"
                continue

            window_start = max(0, position - ESTIMATION_WINDOW)
            historical_target = target_returns.iloc[window_start:position].to_numpy(dtype=float)
            historical_benchmark = benchmark.iloc[window_start:position].to_numpy(dtype=float)
            paired = np.isfinite(historical_target) & np.isfinite(historical_benchmark)
            observations_used = int(paired.sum())
            if observations_used < MINIMUM_PAIRED_OBSERVATIONS:
                failures[(symbol, position)] = "insufficient_paired_observations"
                continue

            target_values = historical_target[paired]
            benchmark_values = historical_benchmark[paired]
            benchmark_variance = float(np.var(benchmark_values, ddof=1))
            if (
                not np.isfinite(benchmark_variance)
                or benchmark_variance <= NUMERICAL_ZERO_TOLERANCE
            ):
                failures[(symbol, position)] = "zero_benchmark_variance"
                continue

            covariance = float(np.cov(target_values, benchmark_values, ddof=1)[0, 1])
            beta = covariance / benchmark_variance
            alpha = float(np.mean(target_values) - beta * np.mean(benchmark_values))
            fitted_residuals = target_values - (alpha + beta * benchmark_values)
            residual_volatility = float(np.std(fitted_residuals, ddof=1))
            if (
                not np.isfinite(residual_volatility)
                or residual_volatility <= NUMERICAL_ZERO_TOLERANCE
            ):
                failures[(symbol, position)] = "zero_residual_volatility"
                continue

            residual = float(current_target - (alpha + beta * current_benchmark))
            paired_positions = np.flatnonzero(paired) + window_start
            estimates[(symbol, position)] = _DailyEstimate(
                residual=residual,
                alpha=alpha,
                beta=beta,
                residual_volatility=residual_volatility,
                observations_used=observations_used,
                lookback_start=dates[int(paired_positions[0])],
                lookback_end=dates[int(paired_positions[-1])],
            )

    return estimates, failures


def calculate_sector_divergence(
    inputs: SectorDivergenceInputs,
    *,
    computed_at: datetime | None = None,
) -> SectorDivergenceCalculation:
    """Calculate deterministic divergence scores for the input signal date only."""
    calculation_time = computed_at or datetime.now(UTC)
    _validate_inputs(inputs, calculation_time)

    prices = inputs.adjusted_closes.sort_index().loc[: inputs.signal_date].copy()
    symbols = sorted(inputs.security_ids)
    prices = prices.reindex(columns=symbols)
    opens = (
        inputs.adjusted_opens.sort_index().loc[: inputs.signal_date].reindex(columns=symbols).copy()
        if inputs.adjusted_opens is not None
        else None
    )
    industries = {symbol: inputs.industries[symbol] for symbol in symbols}
    estimates, failures = _calculate_daily_estimates(prices, industries, opens=opens)
    issues: list[CalculationIssue] = []
    dates = list(prices.index)
    signal_position = dates.index(inputs.signal_date)
    provisional_scores: list[DivergenceScore] = []

    for symbol in symbols:
        security_id = inputs.security_ids[symbol]
        estimate = estimates.get((symbol, signal_position))
        if estimate is None:
            reason = failures.get((symbol, signal_position), "daily_estimate_unavailable")
            issues.append(
                CalculationIssue(
                    security_id=security_id,
                    symbol=symbol,
                    signal_date=inputs.signal_date,
                    reason=reason,
                    details=f"The {reason.replace('_', ' ')} requirement was not satisfied",
                )
            )
            continue

        adjustment_value = inputs.adjustment_versions.at[inputs.signal_date, symbol]
        adjustment_version = str(adjustment_value)
        for horizon in HORIZONS:
            first_position = signal_position - horizon + 1
            residual_estimates = [
                estimates.get((symbol, position))
                for position in range(first_position, signal_position + 1)
            ] if first_position >= 0 else []
            if len(residual_estimates) != horizon or any(
                residual_estimate is None for residual_estimate in residual_estimates
            ):
                issues.append(
                    CalculationIssue(
                        security_id=security_id,
                        symbol=symbol,
                        signal_date=inputs.signal_date,
                        horizon=horizon,
                        reason="insufficient_horizon_residuals",
                        details=f"Required {horizon} consecutive point-in-time residuals",
                    )
                )
                continue

            residual_sum = sum(
                residual_estimate.residual
                for residual_estimate in residual_estimates
                if residual_estimate is not None
            )
            divergence = residual_sum / (estimate.residual_volatility * sqrt(horizon))
            provisional_scores.append(
                DivergenceScore(
                    security_id=security_id,
                    symbol=symbol,
                    signal_date=inputs.signal_date,
                    industry=industries[symbol],
                    horizon=horizon,
                    residual_value=residual_sum,
                    divergence_value=divergence,
                    alpha=estimate.alpha,
                    beta=estimate.beta,
                    residual_volatility=estimate.residual_volatility,
                    industry_percentile=0.0,
                    interpretation=_interpret(divergence),
                    lookback_start=estimate.lookback_start,
                    lookback_end=estimate.lookback_end,
                    observations_used=estimate.observations_used,
                    data_cutoff=inputs.data_cutoff,
                    membership_source=inputs.membership_sources[symbol],
                    adjustment_version=adjustment_version,
                    implementation_version=FORMULA_VERSION,
                    computed_at=calculation_time,
                )
            )

    grouped_values: dict[tuple[str, int], list[float]] = {}
    for score in provisional_scores:
        grouped_values.setdefault((score.industry, score.horizon), []).append(
            score.divergence_value
        )
    for values in grouped_values.values():
        values.sort()

    scored = [
        replace(
            score,
            industry_percentile=(
                100.0
                * bisect_right(
                    grouped_values[(score.industry, score.horizon)],
                    score.divergence_value,
                )
                / len(grouped_values[(score.industry, score.horizon)])
            ),
        )
        for score in provisional_scores
    ]
    scored.sort(key=lambda item: (item.signal_date, item.industry, item.symbol, item.horizon))
    issues.sort(
        key=lambda item: (
            item.signal_date,
            item.symbol,
            item.horizon if item.horizon is not None else 0,
            item.reason,
        )
    )
    return SectorDivergenceCalculation(
        signal_date=inputs.signal_date,
        scores=tuple(scored),
        issues=tuple(issues),
        input_exclusions=inputs.exclusions,
    )
