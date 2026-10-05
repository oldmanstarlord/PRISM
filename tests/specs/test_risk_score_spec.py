"""Verification test reproducing the exact worked example in docs/specs/RISK_SCORE_SPEC.md."""

import math


def test_risk_score_worked_example() -> None:
    # 1. Configured weights for 8 dimensions
    all_dimension_weights = {
        "market": 25.0,
        "fundamentals": 20.0,
        "liquidity": 10.0,
        "structure": 10.0,
        "relative": 10.0,
        "governance": 10.0,
        "events": 10.0,
        "macro": 5.0,
    }
    assert sum(all_dimension_weights.values()) == 100.0

    # 2. Available dimensions in the worked example
    active_dimensions = ["market", "liquidity", "relative"]
    avail_weight = sum(all_dimension_weights[d] for d in active_dimensions)
    assert avail_weight == 45.0

    # Data coverage ratio
    coverage = avail_weight / 100.0
    assert coverage == 0.45

    # 3. Component points within dimensions
    # Market dimension: 2 equal-weighted components
    p_m1 = 80.0  # volatility_60d (higher_is_riskier)
    p_m2 = 60.0  # max_drawdown (higher_is_riskier)
    p_market = (p_m1 + p_m2) / 2.0
    assert p_market == 70.0

    # Liquidity dimension: 1 component (lower_is_riskier)
    raw_percentile_l1 = 30.0
    p_l1 = 100.0 - raw_percentile_l1  # 70.0
    p_liquidity = p_l1
    assert p_liquidity == 70.0

    # Relative dimension: 1 component (higher_is_riskier)
    p_r1 = 90.0
    p_relative = p_r1
    assert p_relative == 90.0

    # 4. Final renormalised score calculation
    weighted_sum = (
        all_dimension_weights["market"] * p_market
        + all_dimension_weights["liquidity"] * p_liquidity
        + all_dimension_weights["relative"] * p_relative
    )
    assert weighted_sum == 3350.0

    final_score = weighted_sum / avail_weight
    expected_score = 3350.0 / 45.0
    assert math.isclose(final_score, expected_score, abs_tol=1e-9)
    assert round(final_score, 4) == 74.4444

    # 5. Component contributions to final score
    # Each component's share of total weight:
    w_m1 = (all_dimension_weights["market"] * 0.5) / avail_weight
    w_m2 = (all_dimension_weights["market"] * 0.5) / avail_weight
    w_l1 = (all_dimension_weights["liquidity"] * 1.0) / avail_weight
    w_r1 = (all_dimension_weights["relative"] * 1.0) / avail_weight

    c_m1 = w_m1 * p_m1
    c_m2 = w_m2 * p_m2
    c_l1 = w_l1 * p_l1
    c_r1 = w_r1 * p_r1

    assert math.isclose(c_m1, 22.22222222222222, abs_tol=1e-9)
    assert math.isclose(c_m2, 16.666666666666668, abs_tol=1e-9)
    assert math.isclose(c_l1, 15.555555555555555, abs_tol=1e-9)
    assert math.isclose(c_r1, 20.0, abs_tol=1e-9)

    # Sum of contributions matches final score exactly
    assert math.isclose(c_m1 + c_m2 + c_l1 + c_r1, final_score, abs_tol=1e-9)

    # 6. Top-3 reasons ranked by net point contribution
    reasons = [
        ("M1", "volatility_60d", c_m1),
        ("M2", "max_drawdown", c_m2),
        ("L1", "turnover", c_l1),
        ("R1", "divergence_20d", c_r1),
    ]
    reasons.sort(key=lambda x: x[2], reverse=True)
    top_3 = reasons[:3]

    assert top_3[0][1] == "volatility_60d"
    assert round(top_3[0][2], 2) == 22.22

    assert top_3[1][1] == "divergence_20d"
    assert round(top_3[1][2], 2) == 20.00

    assert top_3[2][1] == "max_drawdown"
    assert round(top_3[2][2], 2) == 16.67
