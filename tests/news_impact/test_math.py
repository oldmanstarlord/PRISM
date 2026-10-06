from __future__ import annotations

import pytest

from backend.app.explain.guardrails import validate_text
from backend.app.news_impact.math import (
    affected_portfolio_weight,
    combine_exposures,
    confidence_is_visible,
    exposure_band,
    historical_reaction_label,
    path_exposure,
    recency_decay,
    spillover_is_eligible,
)


def test_hand_calculated_exposure_and_recency() -> None:
    decay = recency_decay(age_days=30, half_life_days=30)
    assert decay == pytest.approx(0.5)
    assert path_exposure(8, 0.75, decay, 0.5) == pytest.approx(0.15)


def test_hand_calculated_four_paths() -> None:
    # Direct path: age 0d, severity 5.0, weight 1.0, signal 0.9
    decay_0 = recency_decay(0, 30.0)
    direct_exp = path_exposure(5.0, 1.0, decay_0, 0.9)
    assert direct_exp == pytest.approx(0.45)

    # Rule path: age 15d, severity 8.0, weight 0.85, signal 1.0
    decay_15 = recency_decay(15, 30.0)
    rule_exp = path_exposure(8.0, 0.85, decay_15, 1.0)
    assert rule_exp == pytest.approx((8.0 / 10.0) * 0.85 * (0.5 ** 0.5))

    # Macro path: age 30d, severity 6.0, weight 0.70, signal 0.5
    decay_30 = recency_decay(30, 30.0)
    macro_exp = path_exposure(6.0, 0.70, decay_30, 0.5)
    assert macro_exp == pytest.approx(0.6 * 0.7 * 0.5 * 0.5)

    # Spillover path: age 15d, severity 8.0, weight 0.60, signal 0.36
    spillover_exp = path_exposure(8.0, 0.60, decay_15, 0.36)
    assert spillover_exp == pytest.approx((8.0 / 10.0) * 0.60 * (0.5 ** 0.5) * 0.36)

    # MAX combination across all 4 channels
    combined = combine_exposures([direct_exp, rule_exp, macro_exp, spillover_exp])
    assert combined == pytest.approx(rule_exp)


def test_max_combination_prevents_double_counting() -> None:
    assert combine_exposures([0.2, 0.7, 0.4]) == pytest.approx(0.7)


@pytest.mark.parametrize(
    ("score", "expected"), [(0.1, "low"), (0.35, "medium"), (0.65, "high")]
)
def test_exposure_band_thresholds(score: float, expected: str) -> None:
    assert exposure_band(score, 0.35, 0.65) == expected


def test_spillover_below_floor_and_low_confidence_are_hidden() -> None:
    assert not spillover_is_eligible(0.249, 0.25)
    assert spillover_is_eligible(0.25, 0.25)
    assert not confidence_is_visible(0.39, 0.4)
    assert confidence_is_visible(0.4, 0.4)


def test_insufficient_history_is_explicit() -> None:
    assert historical_reaction_label(3, 10) == "insufficient history (n=3)"
    assert historical_reaction_label(9, 10) == "insufficient history (n=9)"

    # With sufficient history (>=10) and returns
    returns = {0: 0.005, 1: -0.012, 5: 0.024}
    label = historical_reaction_label(12, 10, returns)
    assert "historical reaction (n=12" in label
    assert "0d: +0.50%" in label
    assert "1d: -1.20%" in label
    assert "5d: +2.40%" in label


def test_portfolio_overlay_weight_arithmetic() -> None:
    assert affected_portfolio_weight([0.25, 0.15, 0.10]) == pytest.approx(0.5)


def test_considerations_pass_no_advice_guardrail() -> None:
    config = {
        "banned_phrases": [
            "buy",
            "sell",
            "price target",
            "will rise",
            "will fall",
            "guaranteed",
            "caused by",
        ]
    }
    # Standard considerations from E4 config
    templates = [
        "Check the portfolio weight held in the affected industries.",
        "Review whether exposed holdings share an MST cluster with a directly named stock.",
        "Monitor the linked macro indicators and their current stored regime.",
    ]
    for text in templates:
        validate_text(text, config)

    # Prohibited phrases must raise ValueError
    with pytest.raises(ValueError, match="banned phrase"):
        validate_text("Buy the affected stock.", config)
    with pytest.raises(ValueError, match="banned phrase"):
        validate_text("Stock price target is 500.", config)
    with pytest.raises(ValueError, match="banned phrase"):
        validate_text("This was caused by the regulatory shock.", config)


def test_evidence_present_on_every_row() -> None:
    from pydantic import ValidationError

    from backend.app.news_impact.schemas import NewsImpactPathOut

    # Valid path with evidence
    path = NewsImpactPathOut(
        path_type="rule",
        direction="headwind",
        severity=8.0,
        exposure_score=0.48,
        exposure_band="medium",
        confidence=0.85,
        evidence=[{"source_table": "policy_rule", "source_ref": "rule-1"}],
    )
    assert len(path.evidence) >= 1

    # Empty evidence must raise ValidationError
    with pytest.raises(ValidationError):
        NewsImpactPathOut(
            path_type="rule",
            direction="headwind",
            severity=8.0,
            exposure_score=0.48,
            exposure_band="medium",
            confidence=0.85,
            evidence=[],
        )
