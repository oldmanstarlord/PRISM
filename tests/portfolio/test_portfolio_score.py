"""Hand-calculated and deterministic tests for Step 12 portfolio scoring."""

import pytest

from backend.app.portfolio.score import HoldingScoreInput, compute_portfolio_score


def test_portfolio_score_separates_holdings_structure_and_confidence_cap() -> None:
    holdings = [
        HoldingScoreInput("AAA", 0.60, 80.0, 90.0),
        HoldingScoreInput("BBB", 0.40, 20.0, 40.0),
    ]
    config = {
        "portfolio_score_weights": {"holding_risk": 0.80, "structure": 0.20},
        "portfolio_structure_weights": {
            "cluster_concentration": 0.50,
            "effective_bets": 0.50,
        },
        "large_holding_weight_threshold": 0.10,
    }

    result = compute_portfolio_score(
        holdings,
        enb_risk_entropy=1.5,
        maximum_cluster_weight=0.70,
        config=config,
    )

    assert result.holding_risk_score == pytest.approx(56.0)
    assert result.structure_components["cluster_concentration"] == pytest.approx(70.0)
    assert result.structure_components["effective_bets"] == pytest.approx(25.0)
    assert result.structure_score == pytest.approx(47.5)
    assert result.total_score == pytest.approx(54.3)
    assert result.weighted_holding_confidence == pytest.approx(70.0)
    assert result.weakest_large_holding_confidence == pytest.approx(40.0)
    assert result.confidence == pytest.approx(40.0)
    assert result == compute_portfolio_score(
        holdings,
        enb_risk_entropy=1.5,
        maximum_cluster_weight=0.70,
        config=config,
    )


def test_missing_structure_renormalises_score_and_lowers_confidence() -> None:
    result = compute_portfolio_score(
        [HoldingScoreInput("AAA", 1.0, 65.0, 80.0)],
        enb_risk_entropy=None,
        maximum_cluster_weight=None,
        config={
            "portfolio_score_weights": {"holding_risk": 0.80, "structure": 0.20},
            "large_holding_weight_threshold": 0.10,
        },
    )

    assert result.total_score == pytest.approx(65.0)
    assert result.coverage == pytest.approx(0.80)
    assert result.confidence == pytest.approx(64.0)
    assert result.status == "partial"
