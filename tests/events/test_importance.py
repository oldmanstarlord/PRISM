"""Tests for event importance scoring formula resolving OQ-9."""

from __future__ import annotations

from backend.app.events.importance import (
    calculate_event_importance,
)


def test_hand_calculated_importance_cases() -> None:
    """Hand-calculated cases: min(10.0, max(1.0, base_weight * magnitude_multiplier))."""
    # 1. Regulatory action standard penalty: base=10.0, mult=1.5 -> raw=15.0 -> capped at 10.0
    imp, comps = calculate_event_importance(
        event_type="regulatory_action",
        headline="SEBI imposes monetary penalty on compliance failure",
    )
    assert imp == 10.0
    assert comps["raw_score"] == 15.0
    assert comps["normalized_importance"] == 10.0
    assert comps["magnitude_multiplier"] == 1.5

    # 2. Debt rating standard: base=8.5, mult=1.0 -> 8.5
    imp, comps = calculate_event_importance(
        event_type="debt_rating",
        headline="Rating agency reviews credit outlook",
    )
    assert imp == 8.5
    assert comps["raw_score"] == 8.5

    # 3. Debt default: base=8.5, mult=2.0 -> 17.0 -> capped at 10.0
    imp, comps = calculate_event_importance(
        event_type="debt_rating",
        headline="Notice of default in debt servicing and bond coupon",
    )
    assert imp == 10.0
    assert comps["magnitude_multiplier"] == 2.0

    # 4. Management resignation of CFO: base=7.0, mult=1.3 -> 9.1
    imp, comps = calculate_event_importance(
        event_type="management_change",
        headline="Resignation of Chief Financial Officer Nilanjan Roy",
    )
    assert imp == 9.1
    assert comps["magnitude_multiplier"] == 1.3

    # 5. Management resignation of Auditor: base=7.0, mult=1.5 -> 10.0 (capped at 10.0)
    imp, comps = calculate_event_importance(
        event_type="management_change",
        headline="Resignation of Statutory Auditor with immediate effect",
    )
    assert imp == 10.0
    assert comps["raw_score"] == 10.5
    assert comps["magnitude_multiplier"] == 1.5

    # 6. Dividend: base=3.0, mult=1.0 -> 3.0
    imp, comps = calculate_event_importance(
        event_type="dividend",
        headline="Declaration of Interim Dividend of Rs 6.25 per share",
    )
    assert imp == 3.0

    # 7. Other general category: base=2.0, mult=1.0 -> 2.0
    imp, comps = calculate_event_importance(
        event_type="other",
        headline="General administrative filing",
    )
    assert imp == 2.0


def test_importance_determinism() -> None:
    """Determinism check: same inputs yield exact identical output values (D6)."""
    h = "Resignation of Chief Executive Officer and Managing Director"
    imp1, comps1 = calculate_event_importance("management_change", h)
    imp2, comps2 = calculate_event_importance("management_change", h)

    assert imp1 == imp2
    assert comps1 == comps2
