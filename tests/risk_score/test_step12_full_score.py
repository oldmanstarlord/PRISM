"""Golden and ablation tests for the complete eight-dimension Step 12 score."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from backend.app.risk_score.components.base import ComponentValue
from backend.app.risk_score.coverage import REQUIRED_DIMENSIONS
from backend.app.risk_score.registry import RegisteredComponentDefinition
from backend.app.risk_score.scorer import RiskScorer, SecurityRiskScore

DIMENSION_WEIGHTS = {
    "market": 25.0,
    "liquidity": 10.0,
    "structure": 10.0,
    "relative": 10.0,
    "fundamentals": 20.0,
    "governance": 10.0,
    "events": 10.0,
    "macro": 5.0,
}


def _fixture() -> tuple[
    list[tuple[UUID, str, str]],
    dict[str, RegisteredComponentDefinition],
    dict[str, list[ComponentValue]],
]:
    universe = [
        (UUID(int=index + 1), f"STK_{chr(65 + index)}", "Technology") for index in range(5)
    ]
    definitions: dict[str, RegisteredComponentDefinition] = {}
    values: dict[str, list[ComponentValue]] = {}
    for dimension in REQUIRED_DIMENSIONS:
        component_id = f"{dimension}_test"
        definitions[component_id] = RegisteredComponentDefinition(
            id=None,
            component_id=component_id,
            dimension=dimension,
            name=f"{dimension.title()} test component",
            description="Deterministic Step 12 golden input",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=1,
            weight=1.0,
            active=True,
            introduced_in_step="Step 12 test",
        )
        values[component_id] = [
            ComponentValue(
                security_id=security_id,
                symbol=symbol,
                component_id=component_id,
                raw_value=float((index + 1) * 10),
                status="ok",
                data_as_of=date(2026, 9, 30),
                data_age_days=0,
            )
            for index, (security_id, symbol, _) in enumerate(universe)
        ]
    return universe, definitions, values


def _snapshot(score: SecurityRiskScore) -> dict[str, object]:
    return {
        "symbol": score.symbol,
        "overall_score": score.overall_score,
        "coverage": score.coverage,
        "status": score.status,
        "dimensions": {
            dimension: {"score": item.score, "status": item.status}
            for dimension, item in score.dimensions.items()
        },
        "component_points": {
            component.component_id: component.points for component in score.components
        },
    }


def test_full_stock_score_matches_golden_file_and_is_deterministic() -> None:
    universe, definitions, values = _fixture()
    config = {"dimension_weights": DIMENSION_WEIGHTS, "min_coverage_ratio": 0.70}
    scorer = RiskScorer(config, definitions)

    first = scorer.synthesize(universe, values)
    second = scorer.synthesize(universe, values)
    target_id = universe[2][0]
    actual = _snapshot(first[target_id])
    golden_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "risk_score"
        / "step12_full_score_golden.json"
    )
    expected = json.loads(golden_path.read_text(encoding="utf-8"))

    assert actual == expected
    assert _snapshot(second[target_id]) == actual


def test_ablation_excludes_a_dimension_without_scorer_changes() -> None:
    universe, definitions, values = _fixture()
    definitions = {
        key: definition
        for key, definition in definitions.items()
        if definition.dimension != "events"
    }
    values = {key: value for key, value in values.items() if key in definitions}

    result = RiskScorer(
        {"dimension_weights": DIMENSION_WEIGHTS, "min_coverage_ratio": 0.70}, definitions
    ).synthesize(universe, values)[universe[2][0]]

    assert result.dimensions["events"].status == "missing"
    assert result.coverage == pytest.approx(0.90)
    assert result.overall_score == pytest.approx(50.0)
