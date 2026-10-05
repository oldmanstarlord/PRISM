"""Mathematical and numeric verification tests for macro regression and component formulas."""

from __future__ import annotations

import math

import numpy as np

from backend.app.macro.sensitivity import compute_ols_sensitivity


def test_hand_calculated_worked_example_macro_spec() -> None:
    """Verify exact hand-calculated worked example from MACRO_SPEC.md Section 5.

    XYZ Stock in Oil & Gas during 'stressed' regime (multiplier 1.50):
      1. crude_oil: beta = -0.45, t = -3.21 (|t| >= 1.96 => sig=1) * |z|=4.20 => 1.890
      2. usd_inr:   beta = -0.30, t = -2.15 (|t| >= 1.96 => sig=1) * |z|=2.875 => 0.8625
      3. in_10y:    beta = -0.15, t = -0.80 (|t| < 1.96 => sig=0)  * |z|=0.50 => 0.0
      4. india_vix: beta = -0.22, t = -2.50 (|t| >= 1.96 => sig=1) * |z|=2.80 => 0.616
      5. flows:     beta = +0.10, t = +1.10 (|t| < 1.96 => sig=0)  * |z|=2.25 => 0.0

    Raw Sum: 1.890 + 0.8625 + 0.0 + 0.616 + 0.0 = 3.3685
    Scaled:  3.3685 * 1.50 = 5.05275
    """
    sensitivities = [
        {"series": "crude_oil", "beta": -0.45, "t_stat": -3.21, "z": 4.20},
        {"series": "usd_inr", "beta": -0.30, "t_stat": -2.15, "z": 2.875},
        {"series": "in_10y_yield", "beta": -0.15, "t_stat": -0.80, "z": 0.50},
        {"series": "india_vix", "beta": -0.22, "t_stat": -2.50, "z": 2.80},
        {"series": "fii_dii_net_flows", "beta": 0.10, "t_stat": 1.10, "z": 2.25},
    ]

    t_crit = 1.96
    regime_multiplier = 1.50

    raw_sum = 0.0
    for s in sensitivities:
        is_sig = abs(s["t_stat"]) >= t_crit
        effective_beta = abs(s["beta"]) if is_sig else 0.0
        contrib = effective_beta * s["z"]
        raw_sum += contrib

    assert math.isclose(raw_sum, 3.3685, rel_tol=1e-6)
    scaled_exposure = raw_sum * regime_multiplier
    assert math.isclose(scaled_exposure, 5.05275, rel_tol=1e-6)


def test_regression_synthetic_data_known_beta() -> None:
    """Test parameter recovery of known beta (beta=1.75) on synthetic series."""
    np.random.seed(12345)
    n = 63
    true_beta = 1.75
    true_alpha = 0.002

    x = np.random.normal(0.0, 0.02, size=n)
    noise = np.random.normal(0.0, 0.005, size=n)
    y = true_alpha + true_beta * x + noise

    beta, t_stat, n_obs, p_val, is_sig = compute_ols_sensitivity(
        x_changes=list(x),
        y_returns=list(y),
        min_obs=30,
        t_crit=1.96,
    )

    assert n_obs == 63
    assert math.isclose(beta, true_beta, rel_tol=0.08)  # Recovers 1.75 within sampling noise
    assert t_stat > 10.0  # Highly significant
    assert p_val < 1e-4
    assert is_sig is True


def test_regression_insignificant_noise_series() -> None:
    """Test that independent random noise yields insignificant sensitivity (no forced exposure)."""
    np.random.seed(999)
    n = 63
    x = np.random.normal(0.0, 0.01, size=n)
    y = np.random.normal(0.0, 0.01, size=n)

    beta, t_stat, n_obs, p_val, is_sig = compute_ols_sensitivity(
        x_changes=list(x),
        y_returns=list(y),
        min_obs=30,
        t_crit=1.96,
    )

    assert n_obs == 63
    assert abs(t_stat) < 1.96
    assert p_val > 0.05
    assert is_sig is False


def test_regression_determinism() -> None:
    """Same inputs must produce bit-for-bit identical outputs (D6)."""
    np.random.seed(42)
    x = list(np.random.normal(0.0, 0.01, size=50))
    y = list(np.random.normal(0.0, 0.01, size=50))

    run1 = compute_ols_sensitivity(x, y)
    run2 = compute_ols_sensitivity(x, y)

    assert run1 == run2


def test_regression_insufficient_data_handling() -> None:
    """Less than min_obs returns safe zeroed values without errors."""
    x = [0.01, 0.02, -0.01]
    y = [0.005, 0.01, -0.005]

    beta, t_stat, n_obs, p_val, is_sig = compute_ols_sensitivity(x, y, min_obs=30)
    assert beta == 0.0
    assert t_stat == 0.0
    assert n_obs == 3
    assert p_val == 1.0
    assert is_sig is False
