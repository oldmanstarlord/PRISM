import numpy as np
import pandas as pd
import pytest

from backend.app.portfolio.shock import (
    calculate_mst_path_decay,
    calculate_regression_betas,
)


def test_calculate_regression_betas_hand_calc():
    # Asset A: var = 0.04
    # Asset B: var = 0.09
    # Cov(A, B) = 0.03
    # Let's generate a 2-column returns panel matching these exact sample stats
    # or synthetic series with known Cov/Var
    np.random.seed(42)
    # Target Cov: [[0.04, 0.03], [0.03, 0.09]]
    mean = [0.0, 0.0]
    cov = [[0.04, 0.03], [0.03, 0.09]]
    samples = np.random.multivariate_normal(mean, cov, size=10000)
    df = pd.DataFrame(samples, columns=["ASSET_A", "ASSET_B"])

    betas_a = calculate_regression_betas(df, "ASSET_A")
    assert betas_a["ASSET_A"] == pytest.approx(1.0)
    # beta_B = Cov(B, A) / Var(A) = 0.03 / 0.04 = 0.75
    assert betas_a["ASSET_B"] == pytest.approx(0.75, rel=0.05)

    betas_b = calculate_regression_betas(df, "ASSET_B")
    assert betas_b["ASSET_B"] == pytest.approx(1.0)
    # beta_A = Cov(A, B) / Var(B) = 0.03 / 0.09 = 0.3333
    assert betas_b["ASSET_A"] == pytest.approx(1.0 / 3.0, rel=0.05)


def test_calculate_mst_path_decay():
    # Tree: A - B - C
    # Edge A-B: corr = 0.8
    # Edge B-C: corr = 0.5
    edges = [
        ("A", "B", 0.8),
        ("B", "C", 0.5),
    ]
    target_symbols = ["A", "B", "C"]

    # Shock A
    # A: distance 0 -> 1.0
    # B: distance 1 -> 1.0 * 0.8 = 0.8
    # C: distance 2 -> 0.8 * 0.5 = 0.4
    decays = calculate_mst_path_decay(edges, "A", target_symbols)
    assert decays["A"] == pytest.approx(1.0)
    assert decays["B"] == pytest.approx(0.8)
    assert decays["C"] == pytest.approx(0.4)


def test_calculate_mst_path_decay_negative_correlation():
    # Negative correlation along tree edge truncates propagation to 0.0
    edges = [
        ("A", "B", -0.5),
        ("B", "C", 0.8),
    ]
    target_symbols = ["A", "B", "C"]
    decays = calculate_mst_path_decay(edges, "A", target_symbols)
    assert decays["A"] == pytest.approx(1.0)
    assert decays["B"] == pytest.approx(0.0)
    assert decays["C"] == pytest.approx(0.0)
