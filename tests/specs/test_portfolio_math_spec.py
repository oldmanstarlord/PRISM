"""Verification test reproducing the exact worked example in docs/specs/PORTFOLIO_MATH_SPEC.md."""

import math


def test_portfolio_math_worked_example() -> None:
    # 1. Holdings valuation and weights
    shares_a = 100
    price_a = 50.0
    val_a = shares_a * price_a  # 5,000

    shares_b = 200
    price_b = 20.0
    val_b = shares_b * price_b  # 4,000

    val_cash = 1000.0  # 1,000

    total_val = val_a + val_b + val_cash
    assert total_val == 10000.0

    w_a = val_a / total_val
    w_b = val_b / total_val
    w_cash = val_cash / total_val

    assert w_a == 0.50
    assert w_b == 0.40
    assert w_cash == 0.10
    assert math.isclose(w_a + w_b + w_cash, 1.0)

    # 2. 3-Day daily returns
    r_a = [0.020, -0.010, 0.015]
    r_b = [-0.010, 0.030, 0.005]
    r_cash = [0.0, 0.0, 0.0]

    # Daily portfolio returns: r_p,t = w_a * r_a,t + w_b * r_b,t + w_cash * r_cash,t
    r_p = [w_a * r_a[t] + w_b * r_b[t] + w_cash * r_cash[t] for t in range(3)]

    assert math.isclose(r_p[0], 0.006, abs_tol=1e-9)
    assert math.isclose(r_p[1], 0.007, abs_tol=1e-9)
    assert math.isclose(r_p[2], 0.0095, abs_tol=1e-9)

    # 3. Mean return
    mean_r_p = sum(r_p) / len(r_p)
    assert math.isclose(mean_r_p, 0.0075, abs_tol=1e-9)

    # 4. Sample variance (ddof=1)
    sq_diffs = [(r - mean_r_p) ** 2 for r in r_p]
    assert math.isclose(sq_diffs[0], 0.00000225, abs_tol=1e-12)
    assert math.isclose(sq_diffs[1], 0.00000025, abs_tol=1e-12)
    assert math.isclose(sq_diffs[2], 0.00000400, abs_tol=1e-12)

    sum_sq_diffs = sum(sq_diffs)
    assert math.isclose(sum_sq_diffs, 0.00000650, abs_tol=1e-12)

    sample_var = sum_sq_diffs / (len(r_p) - 1)
    assert math.isclose(sample_var, 0.00000325, abs_tol=1e-12)

    daily_std = math.sqrt(sample_var)
    assert math.isclose(daily_std, 0.0018027756377319946, abs_tol=1e-9)

    # 5. Annualised volatility (252 trading days)
    ann_vol = daily_std * math.sqrt(252)
    assert math.isclose(ann_vol, 0.028618176042508397, abs_tol=1e-6)
    # Check percentage representation ~ 2.8618%
    assert round(ann_vol * 100, 4) == 2.8618
