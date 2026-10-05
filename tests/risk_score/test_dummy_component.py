"""Tests verifying D2 Component Registry.

Adding a new component requires zero changes to Scorer, API schemas, or UI.
"""

from datetime import date
from uuid import UUID, uuid4

import pytest

from backend.app.risk_score.components.base import ComponentValue, RiskContext
from backend.app.risk_score.registry import (
    ComponentRegistry,
    RegisteredComponentDefinition,
)
from backend.app.risk_score.scorer import RiskScorer


class DummyExperimentalComponent:
    """A new custom experimental risk component added without touching core scorer code."""

    key = "dummy_experimental_alpha"
    dimension = "governance"
    direction = "higher_is_riskier"
    required_inputs = ["custom_audit_feed"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        return [
            ComponentValue(
                security_id=sec_id,
                symbol=symbol,
                component_id=self.key,
                raw_value=42.0,
                status="ok",
                data_as_of=as_of,
                data_age_days=0,
                evidence_ref={"source": "external_feed_v1"},
            )
            for sec_id, symbol, _ in universe
        ]


def test_adding_dummy_component_requires_zero_core_changes() -> None:
    # 1. Register new component in ComponentRegistry
    custom_reg = ComponentRegistry()
    custom_reg.register_class(
        DummyExperimentalComponent.key,
        DummyExperimentalComponent,
    )

    dummy_def = RegisteredComponentDefinition(
        id=uuid4(),
        component_id=DummyExperimentalComponent.key,
        dimension=DummyExperimentalComponent.dimension,
        name="Experimental Audit Alpha",
        description="Newly added component without modifying core code",
        direction=DummyExperimentalComponent.direction,
        scope="universe",
        min_group_size=1,
        weight=1.0,
        active=True,
        introduced_in_step="Step X",
    )
    custom_reg._definitions[DummyExperimentalComponent.key] = dummy_def

    # 2. Instantiate and run compute
    comp_instance = custom_reg.get_instance(DummyExperimentalComponent.key)
    assert comp_instance is not None

    sec_id = uuid4()
    universe = [(sec_id, "TEST", "Tech")]
    as_of = date(2026, 1, 15)

    dummy_context = RiskContext(
        session=None,
        as_of=as_of,
        data_cutoff=None,  # type: ignore[arg-type]
        config={},
    )
    comp_vals = comp_instance.compute(as_of, universe, dummy_context)
    assert len(comp_vals) == 1
    assert comp_vals[0].raw_value == 42.0

    # 3. Core RiskScorer processes the newly registered component dynamically
    config = {
        "dimension_weights": {"governance": 10.0},
        "min_coverage_ratio": 0.10,
    }
    scorer = RiskScorer(config, {DummyExperimentalComponent.key: dummy_def})
    results = scorer.synthesize(universe, {DummyExperimentalComponent.key: comp_vals})

    res = results[sec_id]
    assert res.overall_score == pytest.approx(50.0)  # Single observation midpoint
    assert DummyExperimentalComponent.key in [c.component_id for c in res.components]
    assert "governance" in res.dimensions
    assert res.dimensions["governance"].score == pytest.approx(50.0)
