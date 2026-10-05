"""Tests for Component protocol and ComponentRegistry (D2)."""

from typing import Any

from backend.app.risk_score.registry import (
    Component,
    ComponentOutput,
    ComponentRegistry,
    registry,
)


class MockVolatilityComponent:
    """Mock component implementing the Component protocol."""

    component_id = "mock_volatility"
    dimension = "market"
    direction = "higher_is_riskier"
    scope = "universe"
    min_group_size = 5
    weight = 1.0

    def compute(self, context: Any) -> ComponentOutput:
        return ComponentOutput(
            component_id=self.component_id,
            dimension=self.dimension,
            raw_value=0.25,
            percentile_rank=75.0,
            points=75.0,
            status="ok",
        )


def test_component_protocol_conformance() -> None:
    comp = MockVolatilityComponent()
    assert isinstance(comp, Component)
    output = comp.compute({})
    assert output.status == "ok"
    assert output.points == 75.0


def test_registry_seed_components_present() -> None:
    # All 12 seed components should be registered by default
    components = registry.list_components()
    assert len(components) >= 12

    # Check Step 5 price-side components are inactive by default
    vol = registry.get_definition("volatility_60d")
    assert vol is not None
    assert vol.dimension == "market"
    assert vol.active is False
    assert vol.introduced_in_step == "Step 5"

    # Check filtering
    market_comps = registry.list_components(dimension="market")
    assert len(market_comps) == 3
    for c in market_comps:
        assert c.dimension == "market"

    # Active only should return empty since all seeds are inactive
    active_comps = registry.list_components(active_only=True)
    assert len(active_comps) == 0


def test_registry_register_custom_handler() -> None:
    custom_reg = ComponentRegistry()
    mock_handler = MockVolatilityComponent()
    custom_reg.register_handler(mock_handler)
    assert custom_reg.get_handler("mock_volatility") is mock_handler
