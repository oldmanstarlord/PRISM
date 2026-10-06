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


def test_portfolio_overlay_weight_arithmetic() -> None:
    assert affected_portfolio_weight([0.25, 0.15, 0.10]) == pytest.approx(0.5)


def test_considerations_pass_no_advice_guardrail() -> None:
    config = {
        "banned_phrases": ["buy", "sell", "price target", "will rise", "guaranteed"]
    }
    validate_text("Check the portfolio weight held in affected industries.", config)
    with pytest.raises(ValueError, match="banned phrase"):
        validate_text("Buy the affected stock.", config)
