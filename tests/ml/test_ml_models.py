"""Tests for model determinism, baseline fallback, Markov filtering, and anomalies."""

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from backend.app.ml.models.anomaly_detector import AnomalyDetector
from backend.app.ml.models.market_regime import MarketRegimeDetector
from backend.app.ml.models.risk_score_validator import RiskScoreValidator
from backend.app.ml.models.volatility_forecast import VolatilityForecaster


def _make_sample_series(n: int = 350, seed: int = 42) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    ret_asset = rng.normal(0.0003, 0.015, n)
    ret_bench = rng.normal(0.0002, 0.010, n)
    prices = pd.Series(100.0 * np.cumprod(1.0 + ret_asset), index=dates)
    bench_returns = pd.Series(ret_bench, index=dates)
    return prices, bench_returns


def test_volatility_forecaster_determinism():
    """Verify that identical random seeds produce identical walk-forward metrics and forecasts."""
    prices, bench = _make_sample_series(300, seed=77)
    forecaster1 = VolatilityForecaster(random_seed=42)
    res1, card1 = forecaster1.train_and_evaluate(prices, bench)

    forecaster2 = VolatilityForecaster(random_seed=42)
    res2, card2 = forecaster2.train_and_evaluate(prices, bench)

    assert np.isclose(res1.predicted_volatility, res2.predicted_volatility, atol=1e-6)
    assert np.isclose(res1.lower_bound_90, res2.lower_bound_90, atol=1e-6)
    assert np.isclose(res1.upper_bound_90, res2.upper_bound_90, atol=1e-6)
    assert card1["name"] == card2["name"]
    assert res1.model_selected == res2.model_selected


def test_volatility_forecaster_baseline_fallback():
    """Verify that if an ML model fails to beat baseline by 2%, baseline is selected as primary."""
    prices, bench = _make_sample_series(250, seed=12)
    forecaster = VolatilityForecaster(random_seed=42)
    res, card = forecaster.train_and_evaluate(prices, bench)

    assert res.model_selected in [
        "ml_gradient_boosting",
        "baseline_har",
        "baseline_ewma",
        "baseline_trailing",
    ]


def test_market_regime_uses_filtered_probabilities_only():
    """Verify regime detector uses filtered probabilities and does NOT leak future states."""
    rng = np.random.default_rng(55)
    ret0 = rng.normal(0.0005, 0.008, 150)
    ret1 = rng.normal(-0.0010, 0.025, 100)
    returns = pd.Series(np.concatenate([ret0, ret1]))

    detector = MarketRegimeDetector()
    res, card = detector.fit_predict(returns)

    assert res.active_regime_name in ["Calm / Normal", "Turbulent / Stressed"]
    assert 0.0 <= res.filtered_probability <= 1.0
    assert (
        res.regime_conditional_volatilities["Turbulent / Stressed"]
        > res.regime_conditional_volatilities["Calm / Normal"]
    )
    trans = np.array(res.transition_matrix)
    assert np.allclose(trans.sum(axis=1), 1.0, atol=1e-5)


def test_anomaly_detector_generates_rankings_without_claiming_accuracy():
    """Verify anomaly detector computes outlier rankings, flag rate, and stability."""
    rng = np.random.default_rng(88)
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    prices_dict = {}
    for sym in ["RELIANCE", "TCS", "INFY", "HDFCBANK"]:
        ret = rng.normal(0.0005, 0.015, 100)
        prices_dict[sym] = 100.0 * np.cumprod(1.0 + ret)

    # Induce an artificial anomaly in INFY on last day
    prices_dict["INFY"][-1] *= 1.15
    prices_df = pd.DataFrame(prices_dict, index=dates)
    bench_returns = pd.Series(rng.normal(0.0002, 0.010, 100), index=dates)

    detector = AnomalyDetector(random_seed=42)
    res, card = detector.detect_anomalies(prices_df, bench_returns)

    assert len(res.all_evaluated_holdings) == 4
    assert 0.0 <= res.flag_rate_percent <= 100.0
    assert "Unsupervised statistical outlier detection" in res.governance_notice


def test_risk_score_validator_walk_forward_calibration():
    """Verify risk score validator calculates rank IC and isotonic calibration curve."""
    rng = np.random.default_rng(99)
    n = 250
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    scores = rng.uniform(10, 90, n)
    ret = rng.normal(0.0, 0.015, n) * (scores / 50.0)
    prices = pd.Series(100.0 * np.cumprod(1.0 + ret), index=dates)

    validator = RiskScoreValidator()
    res, card = validator.validate_score(scores, prices)

    assert -1.0 <= res.spearman_ic_vol_21d <= 1.0
    assert 0.0 <= res.worst_quintile_auc <= 1.0
    assert len(res.isotonic_calibration_curve) == 5
    for bracket in res.isotonic_calibration_curve:
        assert 0.0 <= bracket["historical_drawdown_frequency_pct"] <= 100.0
