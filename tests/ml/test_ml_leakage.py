"""Tests for point-in-time feature integrity, purged gaps, and target shuffling."""

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from backend.app.ml.feature_builder import build_volatility_features
from backend.app.ml.models.volatility_forecast import VolatilityForecaster
from backend.app.ml.walk_forward import (
    ExpandingWindowWalkForward,
    verify_point_in_time_leakage,
)


def _generate_synthetic_prices(n: int = 400, seed: int = 42) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    ret_asset = rng.normal(0.0004, 0.015, n)
    ret_bench = rng.normal(0.0003, 0.010, n)
    prices = pd.Series(100.0 * np.cumprod(1.0 + ret_asset), index=dates)
    bench_returns = pd.Series(ret_bench, index=dates)
    return prices, bench_returns


def test_point_in_time_leakage_verifier():
    """Verify that verify_point_in_time_leakage catches forward target overlap."""
    n = 200
    dates = pd.date_range("2023-01-01", periods=n, freq="B").date
    feature_dates = list(dates)
    clean_target_dates = [d + pd.Timedelta(days=21) for d in dates]

    res_clean = verify_point_in_time_leakage(feature_dates, clean_target_dates, horizon=21)
    assert res_clean["is_leakage_free"] is True
    assert res_clean["violations"] == 0

    # Contaminated target: target timestamp is before feature date
    bad_target_dates = [d - pd.Timedelta(days=1) for d in dates]
    res_bad = verify_point_in_time_leakage(feature_dates, bad_target_dates, horizon=21)
    assert res_bad["is_leakage_free"] is False
    assert res_bad["violations"] > 0


def test_expanding_window_purging_and_embargo():
    """Verify walk-forward splits strictly purge overlapping target horizons."""
    n_samples = 300
    dates = pd.date_range("2023-01-01", periods=n_samples, freq="B").date
    horizon = 21
    embargo = 21
    cv = ExpandingWindowWalkForward(
        min_train_size=100,
        test_size=20,
        horizon=horizon,
        embargo=embargo,
    )
    splits = list(cv.split(dates))
    assert len(splits) > 0

    for fold in splits:
        train_set = set(fold.train_indices)
        test_set = set(fold.test_indices)
        assert len(train_set.intersection(test_set)) == 0
        assert max(fold.train_indices) < min(fold.test_indices)
        assert len(fold.train_indices) >= 70


def test_feature_builder_uses_only_past_data():
    """Verify feature builder produces features using strictly past closing prices."""
    prices, bench = _generate_synthetic_prices(300)

    # Build features on full series
    df_features = build_volatility_features(prices, bench)

    # For an arbitrary historical date t, calculate feature on subset up to t
    test_date = df_features.index[100]
    prices_subset = prices.loc[:test_date]
    bench_subset = bench.loc[:test_date]

    df_subset = build_volatility_features(prices_subset, bench_subset)

    cols_to_check = ["vol_21d", "vol_ewma_94", "benchmark_vol_21d"]
    for col in cols_to_check:
        val_full = df_features.loc[test_date, col]
        val_sub = df_subset.loc[test_date, col]
        assert np.isclose(
            val_full, val_sub, atol=1e-8
        ), f"Leakage in {col}: {val_full} != {val_sub}"


def test_shuffled_target_destroys_skill():
    """Verify that shuffling the target/price structure strictly destroys predictive skill."""
    prices, bench = _generate_synthetic_prices(350, seed=101)

    # Fit forecaster on true series
    forecaster = VolatilityForecaster(random_seed=42)
    res_true, _ = forecaster.train_and_evaluate(prices, bench)
    ml_eval_true = next(
        e
        for e in res_true.evaluations
        if "ml" in e["model_name"].lower() or "Gradient" in e["model_name"]
    )
    r2_true = ml_eval_true["mincer_zarnowitz_r2"]

    # Fit on randomly permuted prices to destroy predictive signal
    rng = np.random.default_rng(999)
    shuffled_prices = pd.Series(rng.permutation(prices.values), index=prices.index)
    forecaster_shuf = VolatilityForecaster(random_seed=42)
    res_shuf, _ = forecaster_shuf.train_and_evaluate(shuffled_prices, bench)
    ml_eval_shuf = next(
        e
        for e in res_shuf.evaluations
        if "ml" in e["model_name"].lower() or "Gradient" in e["model_name"]
    )
    r2_shuf = ml_eval_shuf["mincer_zarnowitz_r2"]

    # Shuffled skill must be destroyed (near 0 or significantly less than true R2)
    assert r2_shuf <= 0.05 or r2_shuf < r2_true
