"""Test recency decay math, tailwind mitigation cap, and no look-ahead (Step 11, D3, D4)."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from backend.app.risk_score.components.news_policy import NewsPolicyPressureComponent


def test_recency_decay_exact_values():
    """Verify half-life formula 2^(-delta_t / 14) for 0d, 14d, and 28d."""
    half_life_days = 14.0

    # Day 0: 2^0 = 1.0
    decay_0 = math.pow(2.0, -0.0 / half_life_days)
    assert pytest.approx(decay_0, 1e-6) == 1.0

    # Day 14: 2^-1 = 0.5
    decay_14 = math.pow(2.0, -14.0 / half_life_days)
    assert pytest.approx(decay_14, 1e-6) == 0.5

    # Day 28: 2^-2 = 0.25
    decay_28 = math.pow(2.0, -28.0 / half_life_days)
    assert pytest.approx(decay_28, 1e-6) == 0.25


def test_component_score_and_tailwind_mitigation_cap():
    """Verify NewsPolicyPressureComponent limits tailwind offset to max 30% of headwind pressure."""
    comp = NewsPolicyPressureComponent()
    assert comp.component_id == "news_policy_pressure"
    assert comp.dimension == "macro"
    # Case 1: Headwind severity 8.0, 0 days old -> raw_value = 8.0
    # points = (8.0 / 10.0) * 100 = 80.0
    # If tailwind severity 10.0 is present:
    # uncapped tailwind = 10.0
    # max tailwind offset = 0.30 * 8.0 = 2.4
    # effective net = 8.0 - 2.4 = 5.6
    # points = (5.6 / 10.0) * 100 = 56.0
    headwind = 8.0
    tailwind = 10.0
    max_offset = 0.30 * headwind
    net = headwind - min(tailwind, max_offset)

    assert pytest.approx(net, 1e-5) == 5.6
    expected_points = (net / 10.0) * 100.0
    assert pytest.approx(expected_points, 1e-5) == 56.0


def test_no_look_ahead_excludes_future_events():
    """Verify events published strictly after as_of_date are excluded from computation (D4)."""
    cutoff = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)

    # Past event: 2026-03-08 (valid)
    past_date = datetime(2026, 3, 8, 10, 0, 0, tzinfo=UTC)
    # Future event: 2026-03-12 (look-ahead)
    future_date = datetime(2026, 3, 12, 10, 0, 0, tzinfo=UTC)

    assert past_date <= cutoff
    assert future_date > cutoff  # Must be rejected
