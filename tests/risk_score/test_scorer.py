"""Tests for RiskScorer, weak percentile ranking, and renormalisation (D1, D2)."""

from datetime import date
from uuid import uuid4

import pytest

from backend.app.risk_score.components.base import ComponentValue
from backend.app.risk_score.registry import RegisteredComponentDefinition
from backend.app.risk_score.scorer import (
    RiskScorer,
    compute_weak_percentile,
)


def test_weak_empirical_percentile_calculation() -> None:
    # 5 items: 10, 20, 30, 40, 50
    peers = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert compute_weak_percentile(10.0, peers) == pytest.approx(10.0)
    assert compute_weak_percentile(20.0, peers) == pytest.approx(30.0)
    assert compute_weak_percentile(30.0, peers) == pytest.approx(50.0)
    assert compute_weak_percentile(40.0, peers) == pytest.approx(70.0)
    assert compute_weak_percentile(50.0, peers) == pytest.approx(90.0)

    # Identical values get identical midpoints
    tied_peers = [10.0, 10.0, 20.0, 20.0]
    # For 10.0: less=0, equal=2 => 100 * (0 + 1) / 4 = 25.0
    assert compute_weak_percentile(10.0, tied_peers) == pytest.approx(25.0)
    # For 20.0: less=2, equal=2 => 100 * (2 + 1) / 4 = 75.0
    assert compute_weak_percentile(20.0, tied_peers) == pytest.approx(75.0)


def test_5_stock_hand_calculated_percentile_and_weights() -> None:
    """5-stock example with directional handling and dimension weighting."""
    universe = [
        (uuid4(), "STK_A", "Tech"),
        (uuid4(), "STK_B", "Tech"),
        (uuid4(), "STK_C", "Tech"),
        (uuid4(), "STK_D", "Tech"),
        (uuid4(), "STK_E", "Tech"),
    ]

    # Two components in market dimension:
    # C1 (higher_is_riskier): 10, 20, 30, 40, 50 -> percentiles 10, 30, 50, 70, 90
    # C2 (lower_is_riskier):  50, 40, 30, 20, 10 -> points 10, 30, 50, 70, 90
    definitions = {
        "comp_vol": RegisteredComponentDefinition(
            id=None,
            component_id="comp_vol",
            dimension="market",
            name="Realised Volatility",
            description="Test volatility",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=5,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
        "comp_liquidity": RegisteredComponentDefinition(
            id=None,
            component_id="comp_liquidity",
            dimension="market",
            name="Liquidity Metric",
            description="Test liquidity",
            direction="lower_is_riskier",
            scope="universe",
            min_group_size=5,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
    }

    as_of = date(2026, 1, 15)
    vol_values = [10.0, 20.0, 30.0, 40.0, 50.0]
    liq_values = [50.0, 40.0, 30.0, 20.0, 10.0]

    vals_by_key = {
        "comp_vol": [
            ComponentValue(
                security_id=universe[i][0],
                symbol=universe[i][1],
                component_id="comp_vol",
                raw_value=vol_values[i],
                status="ok",
                data_as_of=as_of,
                data_age_days=0,
            )
            for i in range(5)
        ],
        "comp_liquidity": [
            ComponentValue(
                security_id=universe[i][0],
                symbol=universe[i][1],
                component_id="comp_liquidity",
                raw_value=liq_values[i],
                status="ok",
                data_as_of=as_of,
                data_age_days=0,
            )
            for i in range(5)
        ],
    }

    config = {
        "dimension_weights": {"market": 25.0},
        "min_coverage_ratio": 0.20,
    }
    scorer = RiskScorer(config, definitions)
    results = scorer.synthesize(universe, vals_by_key)

    # For STK_A (lowest vol = 10, highest liq = 50 => lowest risk):
    # comp_vol points = 10, comp_liquidity points = 100 - 90 = 10.
    # overall_score = 10.0
    res_a = results[universe[0][0]]
    assert res_a.overall_score == pytest.approx(10.0)

    # For STK_C (median vol = 30, median liq = 30):
    # comp_vol points = 50, comp_liquidity points = 100 - 50 = 50.
    # overall_score = 50.0
    res_c = results[universe[2][0]]
    assert res_c.overall_score == pytest.approx(50.0)

    # For STK_E (highest vol = 50, lowest liq = 10 => highest risk):
    # comp_vol points = 90, comp_liquidity points = 100 - 10 = 90.
    # overall_score = 90.0
    res_e = results[universe[4][0]]
    assert res_e.overall_score == pytest.approx(90.0)


def test_missing_dimension_renormalisation_worked_example() -> None:
    """Verify exact worked example from RISK_SCORE_SPEC.md section 6."""
    universe = [(uuid4(), f"STK_{i}", "Finance") for i in range(5)]
    xyz_id = universe[3][0]  # Target stock XYZ is index 3

    # Market: W=25, equal-weight components M1 (pct 80.0) and M2 (pct 60.0) => Dim score = 70.0
    # Liquidity: W=10, L1 (lower_is_riskier, pct 30.0 => points 70.0) => Dim score = 70.0
    # Relative: W=10, R1 (pct 90.0) => Dim score = 90.0
    definitions = {
        "m1": RegisteredComponentDefinition(
            id=None,
            component_id="m1",
            dimension="market",
            name="M1",
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
        "m2": RegisteredComponentDefinition(
            id=None,
            component_id="m2",
            dimension="market",
            name="M2",
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
        "l1": RegisteredComponentDefinition(
            id=None,
            component_id="l1",
            dimension="liquidity",
            name="L1",
            description="",
            direction="lower_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
        "r1": RegisteredComponentDefinition(
            id=None,
            component_id="r1",
            dimension="relative",
            name="R1",
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
    }

    # Peer distributions of size 5 yielding exact percentiles for index 3 (XYZ):
    # For M1: [10, 20, 30, 40, 40] -> for 40: less=3, equal=2 => 100*(3 + 1)/5 = 80.0
    # For M2: [10, 20, 30, 30, 50] -> for 30: less=2, equal=2 => 100*(2 + 1)/5 = 60.0
    # For L1: [50, 40, 30, 20, 10] -> for 20: less=1, equal=1 => 30.0 -> points 100-30 = 70.0
    # For R1: [10, 20, 30, 50, 40] -> for 50: less=4, equal=1 => 100*(4 + 0.5)/5 = 90.0
    m1_vals = [10.0, 20.0, 30.0, 40.0, 40.0]
    m2_vals = [10.0, 20.0, 30.0, 30.0, 50.0]
    l1_vals = [50.0, 40.0, 30.0, 20.0, 10.0]
    r1_vals = [10.0, 20.0, 30.0, 50.0, 40.0]

    as_of = date(2026, 1, 15)
    vals_by_key = {
        "m1": [
            ComponentValue(universe[i][0], universe[i][1], "m1", m1_vals[i], "ok", as_of, 0)
            for i in range(5)
        ],
        "m2": [
            ComponentValue(universe[i][0], universe[i][1], "m2", m2_vals[i], "ok", as_of, 0)
            for i in range(5)
        ],
        "l1": [
            ComponentValue(universe[i][0], universe[i][1], "l1", l1_vals[i], "ok", as_of, 0)
            for i in range(5)
        ],
        "r1": [
            ComponentValue(universe[i][0], universe[i][1], "r1", r1_vals[i], "ok", as_of, 0)
            for i in range(5)
        ],
    }

    config = {
        "dimension_weights": {
            "market": 25.0,
            "fundamentals": 20.0,
            "liquidity": 10.0,
            "structure": 10.0,
            "relative": 10.0,
            "governance": 10.0,
            "events": 10.0,
            "macro": 5.0,
        },
        "min_coverage_ratio": 0.70,
    }

    scorer = RiskScorer(config, definitions)
    results = scorer.synthesize(universe, vals_by_key)
    xyz_score = results[xyz_id]

    # Verify coverage: 45 / 100 = 0.45
    assert xyz_score.coverage == pytest.approx(0.45)

    # Verify dimension scores
    assert xyz_score.dimensions["market"].score == pytest.approx(70.0)
    assert xyz_score.dimensions["liquidity"].score == pytest.approx(70.0)
    assert xyz_score.dimensions["relative"].score == pytest.approx(90.0)

    # Verify overall score: 3350 / 45 = 74.4444...
    expected_score = 3350.0 / 45.0
    assert xyz_score.overall_score == pytest.approx(expected_score, abs=0.01)

    # Verify component contributions sum to overall score
    comp_map = {c.component_id: c for c in xyz_score.components}
    assert comp_map["m1"].contribution == pytest.approx(22.2222, abs=0.01)
    assert comp_map["m2"].contribution == pytest.approx(16.6667, abs=0.01)
    assert comp_map["l1"].contribution == pytest.approx(15.5556, abs=0.01)
    assert comp_map["r1"].contribution == pytest.approx(20.0000, abs=0.01)
    assert sum(c.contribution for c in xyz_score.components) == pytest.approx(expected_score)

    # Verify top-3 reasons order: M1 (22.22), R1 (20.00), M2 (16.67)
    assert len(xyz_score.top_reasons) == 3
    assert xyz_score.top_reasons[0]["component_id"] == "m1"
    assert xyz_score.top_reasons[1]["component_id"] == "r1"
    assert xyz_score.top_reasons[2]["component_id"] == "m2"


def test_missing_dimension_renormalisation_formula() -> None:
    """Verify that renormalisation formula matches RISK_SCORE_SPEC.md exactly."""
    sec_id = uuid4()
    universe = [(sec_id, "TEST", "Tech")]

    definitions = {
        "m1": RegisteredComponentDefinition(
            id=None,
            component_id="m1",
            dimension="market",
            name="M1",
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
        "r1": RegisteredComponentDefinition(
            id=None,
            component_id="r1",
            dimension="relative",
            name="R1",
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
    }

    # Single security => weak percentile = (0 + 0.5)/1 * 100 = 50.0
    vals_by_key = {
        "m1": [
            ComponentValue(
                security_id=sec_id,
                symbol="TEST",
                component_id="m1",
                raw_value=25.0,
                status="ok",
                data_as_of=date(2026, 1, 1),
                data_age_days=0,
            )
        ],
        "r1": [
            ComponentValue(
                security_id=sec_id,
                symbol="TEST",
                component_id="r1",
                raw_value=1.5,
                status="ok",
                data_as_of=date(2026, 1, 1),
                data_age_days=0,
            )
        ],
    }

    # Only Market (W=25) and Relative (W=10) are present out of 100 total weight
    config = {
        "dimension_weights": {
            "market": 25.0,
            "fundamentals": 20.0,
            "liquidity": 10.0,
            "structure": 10.0,
            "relative": 10.0,
            "governance": 10.0,
            "events": 10.0,
            "macro": 5.0,
        },
        "min_coverage_ratio": 0.70,
    }

    scorer = RiskScorer(config, definitions)
    results = scorer.synthesize(universe, vals_by_key)
    res = results[sec_id]

    # Available weights = 25 + 10 = 35. Total = 100.
    # Coverage = 35 / 100 = 0.35
    assert res.coverage == pytest.approx(0.35)
    assert res.status == "insufficient"
    assert "low_data_coverage_35.0%" in res.limitations
    assert "dimension_fundamentals_missing" in res.limitations

    # Both dimensions have points = 50.0 => overall score = 50.0
    assert res.overall_score == pytest.approx(50.0)

    # Component contributions must sum to overall score
    total_contrib = sum(c.contribution for c in res.components)
    assert total_contrib == pytest.approx(res.overall_score)
