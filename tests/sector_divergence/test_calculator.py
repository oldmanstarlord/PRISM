from datetime import UTC, datetime
from math import exp, isclose, sqrt
from uuid import UUID

import numpy as np
import pandas as pd

from backend.app.sector_divergence.calculator import calculate_sector_divergence
from backend.app.sector_divergence.inputs import SectorDivergenceInputs

COMPUTED_AT = datetime(2026, 10, 2, 14, tzinfo=UTC)


def make_inputs(
    *,
    periods: int = 85,
    signal_position: int | None = None,
    include_future: int = 0,
) -> SectorDivergenceInputs:
    total_periods = periods + include_future
    dates = [timestamp.date() for timestamp in pd.bdate_range("2026-01-01", periods=total_periods)]
    symbols = [f"STOCK{number}" for number in range(1, 6)]
    returns = np.zeros((total_periods, len(symbols)), dtype=float)
    for position in range(1, total_periods):
        common = 0.0004 + 0.002 * np.sin(position / 5)
        for offset in range(len(symbols)):
            returns[position, offset] = (
                common + 0.0003 * np.cos(position * (offset + 1) / 4) + offset * 0.00005
            )
    prices = np.empty_like(returns)
    prices[0, :] = 100.0
    for position in range(1, total_periods):
        prices[position, :] = prices[position - 1, :] * np.exp(returns[position, :])

    panel = pd.DataFrame(prices, index=pd.Index(dates, name="trade_date"), columns=symbols)
    versions = pd.DataFrame(
        "yfinance-adjclose-v1-r1",
        index=panel.index,
        columns=panel.columns,
    )
    times = pd.DataFrame(COMPUTED_AT, index=panel.index, columns=panel.columns)
    chosen_position = signal_position if signal_position is not None else periods - 1
    return SectorDivergenceInputs(
        signal_date=dates[chosen_position],
        data_cutoff=COMPUTED_AT,
        adjusted_closes=panel,
        adjustment_versions=versions,
        adjustment_times=times,
        security_ids={symbol: UUID(int=index + 1) for index, symbol in enumerate(symbols)},
        industries={symbol: "Banks" for symbol in symbols},
        membership_sources={symbol: "official-test-snapshot" for symbol in symbols},
        exclusions=(),
        issues=(),
    )


def test_calculation_matches_manual_rolling_ols() -> None:
    inputs = make_inputs()
    calculation = calculate_sector_divergence(inputs, computed_at=COMPUTED_AT)
    score = next(
        item for item in calculation.scores if item.symbol == "STOCK1" and item.horizon == 1
    )

    log_prices = np.log(inputs.adjusted_closes)
    returns = log_prices.diff()
    benchmark = returns[["STOCK2", "STOCK3", "STOCK4", "STOCK5"]].median(axis=1)
    target_window = returns["STOCK1"].iloc[-61:-1].to_numpy(dtype=float)
    benchmark_window = benchmark.iloc[-61:-1].to_numpy(dtype=float)
    expected_beta = float(
        np.cov(target_window, benchmark_window, ddof=1)[0, 1] / np.var(benchmark_window, ddof=1)
    )
    expected_alpha = float(np.mean(target_window) - expected_beta * np.mean(benchmark_window))
    fitted_residuals = target_window - (expected_alpha + expected_beta * benchmark_window)
    expected_sigma = float(np.std(fitted_residuals, ddof=1))
    expected_residual = float(
        returns["STOCK1"].iloc[-1] - (expected_alpha + expected_beta * benchmark.iloc[-1])
    )

    assert isclose(score.beta, expected_beta, rel_tol=1e-12)
    assert isclose(score.alpha, expected_alpha, rel_tol=1e-12)
    assert isclose(score.residual_volatility, expected_sigma, rel_tol=1e-12)
    assert isclose(score.residual_value, expected_residual, rel_tol=1e-12)
    assert isclose(score.divergence_value, expected_residual / expected_sigma, rel_tol=1e-12)
    assert score.observations_used == 60
    assert score.lookback_end < score.signal_date


def test_five_day_score_uses_five_point_in_time_residuals() -> None:
    final_inputs = make_inputs()
    final = calculate_sector_divergence(final_inputs, computed_at=COMPUTED_AT)
    five_day = next(item for item in final.scores if item.symbol == "STOCK1" and item.horizon == 5)
    final_position = len(final_inputs.adjusted_closes) - 1
    residuals: list[float] = []
    for position in range(final_position - 4, final_position + 1):
        daily = calculate_sector_divergence(
            make_inputs(signal_position=position),
            computed_at=COMPUTED_AT,
        )
        one_day = next(
            item for item in daily.scores if item.symbol == "STOCK1" and item.horizon == 1
        )
        residuals.append(one_day.residual_value)

    expected = sum(residuals) / (five_day.residual_volatility * sqrt(5))
    assert isclose(five_day.divergence_value, expected, rel_tol=1e-12)


def test_future_prices_do_not_change_a_prior_signal() -> None:
    without_future = make_inputs(periods=80)
    with_future = make_inputs(periods=80, include_future=5)
    with_future.adjusted_closes.iloc[-5:, :] = 1_000_000.0

    baseline = calculate_sector_divergence(without_future, computed_at=COMPUTED_AT)
    future_changed = calculate_sector_divergence(with_future, computed_at=COMPUTED_AT)

    assert baseline.scores == future_changed.scores
    assert baseline.issues == future_changed.issues


def test_missing_signal_price_produces_explicit_unavailable_reason() -> None:
    inputs = make_inputs()
    inputs.adjusted_closes.at[inputs.signal_date, "STOCK1"] = np.nan

    calculation = calculate_sector_divergence(inputs, computed_at=COMPUTED_AT)

    assert not any(score.symbol == "STOCK1" for score in calculation.scores)
    assert any(
        issue.symbol == "STOCK1" and issue.reason == "missing_current_return"
        for issue in calculation.issues
    )


def test_percentile_uses_weak_empirical_distribution() -> None:
    calculation = calculate_sector_divergence(make_inputs(), computed_at=COMPUTED_AT)
    one_day = [score for score in calculation.scores if score.horizon == 1]
    values = sorted(score.divergence_value for score in one_day)

    for score in one_day:
        expected = 100 * sum(value <= score.divergence_value for value in values) / len(values)
        assert score.industry_percentile == expected


def test_constant_peer_benchmark_is_rejected() -> None:
    inputs = make_inputs()
    dates = list(inputs.adjusted_closes.index)
    constant_return = 0.001
    for symbol in ("STOCK2", "STOCK3", "STOCK4", "STOCK5"):
        inputs.adjusted_closes[symbol] = [
            100 * exp(constant_return * position) for position in range(len(dates))
        ]

    calculation = calculate_sector_divergence(inputs, computed_at=COMPUTED_AT)

    assert any(
        issue.symbol == "STOCK1" and issue.reason == "zero_benchmark_variance"
        for issue in calculation.issues
    )
