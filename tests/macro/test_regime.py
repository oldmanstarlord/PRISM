"""Tests for rule-based market regime classification and hysteresis state machine (FR-F4)."""

from __future__ import annotations

from backend.app.macro.regime import DEFAULT_REGIME_CONFIG, evaluate_regime_state


def test_regime_classification_calm_conditions() -> None:
    """Low volatility and low correlation classify into 'calm'."""
    regime, reason = evaluate_regime_state(
        vol_pctl=25.0,
        corr_pctl=30.0,
        vix=12.5,
        prior_regime=None,
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime == "calm"
    assert "calm" in reason


def test_regime_classification_stressed_spike() -> None:
    """Spike in volatility or VIX triggers 'stressed' regime."""
    # Stressed via volatility percentile >= 75
    regime, reason = evaluate_regime_state(
        vol_pctl=80.0,
        corr_pctl=50.0,
        vix=17.0,
        prior_regime="trending",
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime == "stressed"

    # Stressed via VIX >= 22.0
    regime_vix, _ = evaluate_regime_state(
        vol_pctl=50.0,
        corr_pctl=50.0,
        vix=23.5,
        prior_regime="calm",
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime_vix == "stressed"


def test_regime_hysteresis_lock() -> None:
    """In 'stressed' state, minor moderations remain locked in 'stressed' to prevent flickering."""
    # Prior state was stressed; metrics cool slightly from 80% to 70%
    # (still above the 65% exit threshold)
    regime, reason = evaluate_regime_state(
        vol_pctl=70.0,
        corr_pctl=68.0,
        vix=20.0,
        prior_regime="stressed",
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime == "stressed"
    assert reason == "hysteresis_lock_in_stress"


def test_regime_hysteresis_exit_to_trending() -> None:
    """When metrics drop below 65% exit threshold, regime subsides to 'trending'."""
    regime, reason = evaluate_regime_state(
        vol_pctl=60.0,
        corr_pctl=55.0,
        vix=17.5,
        prior_regime="stressed",
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime == "trending"
    assert reason == "stress_subsided_to_trending"


def test_regime_hysteresis_exit_to_calm() -> None:
    """When metrics drop below 35% exit threshold, regime resolves to 'calm'."""
    regime, reason = evaluate_regime_state(
        vol_pctl=30.0,
        corr_pctl=28.0,
        vix=13.0,
        prior_regime="stressed",
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime == "calm"
    assert reason == "stress_resolved_to_calm"


def test_regime_missing_vix_behavior() -> None:
    """Regime classification operates robustly when VIX is unavailable (None)."""
    # Calm without VIX
    regime, _ = evaluate_regime_state(
        vol_pctl=30.0,
        corr_pctl=30.0,
        vix=None,
        prior_regime=None,
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime == "calm"

    # Stressed via vol without VIX
    regime_stress, _ = evaluate_regime_state(
        vol_pctl=85.0,
        corr_pctl=60.0,
        vix=None,
        prior_regime="calm",
        config=DEFAULT_REGIME_CONFIG,
    )
    assert regime_stress == "stressed"


def test_regime_determinism() -> None:
    """Same state inputs must return identical regime state and reason (D6)."""
    r1 = evaluate_regime_state(50.0, 50.0, 16.0, "calm", DEFAULT_REGIME_CONFIG)
    r2 = evaluate_regime_state(50.0, 50.0, 16.0, "calm", DEFAULT_REGIME_CONFIG)
    assert r1 == r2
