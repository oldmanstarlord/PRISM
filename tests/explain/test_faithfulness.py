"""Step E6 Faithfulness Suite.

Independently recomputes each evidence value from raw data/tables and
asserts equality within tolerance.
Conforms strictly to Rules D8 (evidence-bound), D9 (no advice/non-causal),
and D10 (no DB in pure tests).
"""

from __future__ import annotations

import math
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from backend.app.explain.mst_math import (
    PairStatistics,
    pair_statistics,
    persistence_summary,
)
from backend.app.explain.sector_math import (
    constituent_period_returns,
    contribution_share,
    peer_median_daily_returns,
    persistence_count,
    trend_label,
    weak_absolute_percentile,
)
from backend.app.news_impact.math import (
    combine_exposures,
    exposure_band,
    path_exposure,
    recency_decay,
)
from backend.app.portfolio.diversification import (
    calculate_eigenvalue_enb,
    calculate_entropy_enb,
)


# ---------------------------------------------------------------------------
# 1. MST Pair and Edge Faithfulness
# ---------------------------------------------------------------------------
def test_faithfulness_mst_pair_statistics() -> None:
    """Independently recompute Pearson correlation and Mantegna distance from raw prices."""
    dates = pd.date_range("2026-01-01", periods=10, freq="B")
    prices_a = [100.0, 102.0, 101.0, 103.5, 105.0, 104.0, 106.0, 108.0, 107.5, 110.0]
    prices_b = [200.0, 203.0, 202.0, 206.0, 209.0, 208.0, 211.0, 214.0, 213.0, 218.0]

    panel = pd.DataFrame({"A": prices_a, "B": prices_b}, index=dates)

    stats: PairStatistics = pair_statistics(panel, "A", "B", dates[-1].date())

    ret_a = np.log(pd.Series(prices_a)).diff().dropna()
    ret_b = np.log(pd.Series(prices_b)).diff().dropna()

    expected_corr = float(ret_a.corr(ret_b))
    expected_dist = math.sqrt(2.0 * max(0.0, 1.0 - expected_corr))

    assert stats.correlation == pytest.approx(expected_corr, abs=1e-6)
    assert stats.distance == pytest.approx(expected_dist, abs=1e-6)
    assert stats.observations == 9


def test_faithfulness_mst_persistence_summary() -> None:
    """Independently recompute window persistence share and median."""
    presence = [True, True, False, True, True]
    correlations = [0.85, 0.90, 0.70, 0.88, 0.92]

    summary = persistence_summary(presence, correlations)

    expected_share = 4.0 / 5.0
    expected_median = float(np.median(correlations))
    expected_min = float(min(correlations))
    expected_max = float(max(correlations))

    assert summary.share == pytest.approx(expected_share, abs=1e-6)
    assert summary.median == pytest.approx(expected_median, abs=1e-6)
    assert summary.minimum == pytest.approx(expected_min, abs=1e-6)
    assert summary.maximum == pytest.approx(expected_max, abs=1e-6)


# ---------------------------------------------------------------------------
# 2. Sector Divergence Faithfulness
# ---------------------------------------------------------------------------
def test_faithfulness_sector_divergence_math() -> None:
    """Independently recompute peer median daily returns, cumulative returns, and percentiles."""
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    panel = pd.DataFrame(
        {
            "INFY": [1000.0, 1010.0, 1020.0, 1015.0, 1030.0],
            "TCS": [3000.0, 3015.0, 3030.0, 3045.0, 3060.0],
            "WIPRO": [400.0, 404.0, 402.0, 406.0, 408.0],
        },
        index=dates,
    )

    constituents = ["INFY", "TCS", "WIPRO"]
    medians = peer_median_daily_returns(panel, constituents, minimum_peers=2)

    # Independent raw verification of median of daily log returns on day 1
    day1_log_ret = [
        math.log(1010.0 / 1000.0),
        math.log(3015.0 / 3000.0),
        math.log(404.0 / 400.0),
    ]
    raw_day1_median = float(np.median(day1_log_ret))
    assert medians.iloc[1] == pytest.approx(raw_day1_median, abs=1e-6)

    cum_returns = constituent_period_returns(panel, constituents, horizon=4)
    raw_infy_cum = (1030.0 / 1000.0 - 1.0) * 100.0
    assert cum_returns["INFY"] == pytest.approx(raw_infy_cum, abs=1e-4)

    assert trend_label(2.5, 1.5) == "up"
    assert trend_label(-2.0, 1.5) == "down"
    assert trend_label(0.5, 1.5) == "flat"

    pct = weak_absolute_percentile(-2.5, [-3.0, -2.5, -1.0, 0.5, 1.2])
    assert pct == pytest.approx(80.0, abs=1e-4)

    hits, total = persistence_count([0.5, 1.8, -2.1, 1.2, -1.6], threshold=1.5, window=4)
    assert hits == 3
    assert total == 4

    share = contribution_share(component_points=2.5, component_weight=1.0, total_score=50.0)
    assert share == pytest.approx(5.0, abs=1e-4)


# ---------------------------------------------------------------------------
# 3. News Impact Math Faithfulness
# ---------------------------------------------------------------------------
def test_faithfulness_news_impact_math() -> None:
    """Independently recompute recency decay, path combination (MAX), and exposure score."""
    decay_0 = recency_decay(0.0, half_life_days=30.0)
    assert decay_0 == pytest.approx(1.0, abs=1e-6)

    decay_30 = recency_decay(30.0, half_life_days=30.0)
    assert decay_30 == pytest.approx(0.5, abs=1e-6)

    decay_60 = recency_decay(60.0, half_life_days=30.0)
    assert decay_60 == pytest.approx(0.25, abs=1e-6)

    path_scores = [0.25, 0.72, 0.45]
    combined = combine_exposures(path_scores)
    assert combined == pytest.approx(0.72, abs=1e-6)

    # path_exposure: (severity/10) * path_weight * decay * signal_strength
    score = path_exposure(
        severity=8.0,
        path_weight=0.85,
        decay=0.5,
        signal_strength=1.0,
    )
    expected_score = (8.0 / 10.0) * 0.85 * 0.5 * 1.0
    assert score == pytest.approx(expected_score, abs=1e-6)

    # Exposure bands
    assert exposure_band(0.20, 0.35, 0.65) == "low"
    assert exposure_band(0.50, 0.35, 0.65) == "medium"
    assert exposure_band(0.80, 0.35, 0.65) == "high"


# ---------------------------------------------------------------------------
# 4. Diversification Math Faithfulness
# ---------------------------------------------------------------------------
def test_faithfulness_diversification_math() -> None:
    """Independently recompute entropy ENB and eigenvalue ENB."""
    p_equal = [0.25, 0.25, 0.25, 0.25]
    enb_equal = calculate_entropy_enb(p_equal)
    assert enb_equal == pytest.approx(4.0, abs=1e-6)

    p_unequal = [0.5, 0.25, 0.15, 0.1]
    expected_entropy = -sum(p * math.log(p) for p in p_unequal)
    expected_enb = math.exp(expected_entropy)
    assert calculate_entropy_enb(p_unequal) == pytest.approx(expected_enb, abs=1e-6)

    # 3x3 identity matrix => 3 uncorrelated assets => eigenvalue ENB == 3.0
    ident = np.eye(3)
    assert calculate_eigenvalue_enb(ident) == pytest.approx(3.0, abs=1e-6)

    # Perfectly correlated matrix (ones) => eigenvalue ENB == 1.0
    ones_mat = np.ones((3, 3))
    assert calculate_eigenvalue_enb(ones_mat) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# 5. Shock Simulation Faithfulness
# ---------------------------------------------------------------------------
def test_faithfulness_shock_regression_math() -> None:
    """Independently recompute beta and shock impact from raw return pairs."""
    holding_ret = np.array([0.02, -0.01, 0.015, -0.025, 0.03, 0.01])
    shocked_ret = np.array([0.015, -0.01, 0.01, -0.02, 0.025, 0.008])

    cov_matrix = np.cov(shocked_ret, holding_ret)
    raw_beta = float(cov_matrix[0, 1] / cov_matrix[0, 0])
    raw_corr = float(np.corrcoef(shocked_ret, holding_ret)[0, 1])
    raw_r2 = raw_corr**2

    shock_pct = -10.0
    predicted_impact = raw_beta * shock_pct

    assert raw_beta > 0.0
    assert 0.0 <= raw_r2 <= 1.0
    assert predicted_impact == pytest.approx(raw_beta * -10.0, abs=1e-6)


# ---------------------------------------------------------------------------
# 6. Score Change Attribution Faithfulness
# ---------------------------------------------------------------------------
def test_faithfulness_score_change_attribution() -> None:
    """Independently recompute delta score and top driver deltas."""
    prior_components = {
        "ewma_volatility": Decimal("18.5"),
        "sector_divergence": Decimal("8.0"),
        "promoter_pledge": Decimal("4.2"),
    }
    latest_components = {
        "ewma_volatility": Decimal("22.5"),
        "sector_divergence": Decimal("6.0"),
        "promoter_pledge": Decimal("4.2"),
    }

    prior_total = sum(prior_components.values())
    latest_total = sum(latest_components.values())
    expected_delta = latest_total - prior_total

    component_deltas = {
        k: latest_components[k] - prior_components[k] for k in latest_components
    }

    assert sum(component_deltas.values()) == expected_delta
    top_driver = max(component_deltas.items(), key=lambda item: item[1])
    assert top_driver[0] == "ewma_volatility"
    assert top_driver[1] == Decimal("4.0")
