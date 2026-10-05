import numpy as np
import pytest

from backend.app.portfolio.diversification import (
    analyze_cluster_concentration,
    calculate_eigenvalue_enb,
    calculate_entropy_enb,
)


def test_calculate_eigenvalue_enb_identity():
    # Identity matrix (uncorrelated assets) -> ENB = N
    corr = np.eye(4)
    enb = calculate_eigenvalue_enb(corr)
    assert pytest.approx(enb, rel=1e-4) == 4.0


def test_calculate_eigenvalue_enb_perfect_correlation():
    # Perfectly correlated assets (rank 1) -> ENB = 1.0
    corr = np.ones((4, 4))
    enb = calculate_eigenvalue_enb(corr)
    assert pytest.approx(enb, rel=1e-4) == 1.0


def test_calculate_entropy_enb_equal_risk():
    # Equal risk contributions across N assets -> ENB = N
    rc = [0.25, 0.25, 0.25, 0.25]
    enb = calculate_entropy_enb(rc)
    assert pytest.approx(enb, rel=1e-4) == 4.0


def test_calculate_entropy_enb_single_asset_risk():
    # 100% risk concentrated in 1 asset -> ENB = 1.0
    rc = [1.0, 0.0, 0.0]
    enb = calculate_entropy_enb(rc)
    assert pytest.approx(enb, rel=1e-4) == 1.0


def test_calculate_entropy_enb_with_negative_contributions():
    # Negative risk contributions (hedging assets) are clipped/handled safely
    rc = [0.8, 0.4, -0.2]
    enb = calculate_entropy_enb(rc)
    assert 1.0 <= enb <= 3.0


def test_analyze_cluster_concentration():
    holdings = [
        {"symbol": "TCS", "weight": 0.45},
        {"symbol": "INFY", "weight": 0.35},
        {"symbol": "RELIANCE", "weight": 0.20},
    ]
    # TCS and INFY in cluster 1 (total 0.80 > 0.40 threshold)
    symbol_to_cluster = {
        "TCS": "cluster-1",
        "INFY": "cluster-1",
        "RELIANCE": "cluster-2",
    }

    cluster_weights, findings = analyze_cluster_concentration(
        holdings=holdings,
        symbol_to_cluster=symbol_to_cluster,
        high_concentration_threshold=0.40,
    )

    assert cluster_weights["cluster-1"] == pytest.approx(0.80)
    assert cluster_weights["cluster-2"] == pytest.approx(0.20)
    assert len(findings) > 0
    assert findings[0]["severity"] == "high"
    assert "cluster-1" in findings[0]["message"]
    # Check compliance: never provide investment advice or say 'buy'
    for f in findings:
        msg = f["message"].lower()
        assert "buy" not in msg
        assert "sell" not in msg
