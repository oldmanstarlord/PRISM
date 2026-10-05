"""Verification test reproducing the exact worked example in docs/specs/CONFIDENCE_SPEC.md."""

import math


def test_confidence_score_worked_example() -> None:
    # 1. Six confidence factors (each in [0, 1])
    f_coverage = 0.45
    f_freshness = 0.90
    f_source = 1.00
    f_signal = 0.80
    f_stability = 0.95
    f_volume = 1.00

    factors = [f_coverage, f_freshness, f_source, f_signal, f_stability, f_volume]
    assert len(factors) == 6

    # 2. Equal weights (w = 1.0 each)
    factor_sum = sum(factors)
    assert math.isclose(factor_sum, 5.10, abs_tol=1e-9)

    mean_factor = factor_sum / len(factors)
    assert math.isclose(mean_factor, 0.85, abs_tol=1e-9)

    c_raw = 100.0 * mean_factor
    assert math.isclose(c_raw, 85.0, abs_tol=1e-9)

    # 3. Integrity Caps evaluation
    # Cap 1: Stale price cap (stale_price_days = 5, cap = 50.0)
    data_age_days = 1
    stale_price_cap = 50.0
    stale_cap_triggered = data_age_days > 5
    assert not stale_cap_triggered

    # Cap 2: Low coverage cap (threshold = 0.70, cap = 60.0)
    coverage_threshold = 0.70
    low_coverage_cap = 60.0
    coverage_cap_triggered = f_coverage < coverage_threshold
    assert coverage_cap_triggered

    active_caps = []
    if stale_cap_triggered:
        active_caps.append(stale_price_cap)
    if coverage_cap_triggered:
        active_caps.append(low_coverage_cap)

    assert len(active_caps) == 1
    assert active_caps[0] == 60.0

    # 4. Final constrained confidence
    c_final = min([c_raw] + active_caps)
    assert c_final == 60.0
