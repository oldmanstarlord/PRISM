"""Regression tests for the Step 12 eight-dimension coverage contract."""

from backend.app.risk_score.coverage import (
    COVERAGE_MATRIX,
    REQUIRED_DIMENSIONS,
    validate_coverage_matrix,
)
from backend.app.risk_score.registry import BUILTIN_COMPONENT_CLASSES


def test_every_required_dimension_is_explicit() -> None:
    assert tuple(COVERAGE_MATRIX) == REQUIRED_DIMENSIONS
    assert validate_coverage_matrix() == []


def test_every_declared_active_component_has_an_implementation() -> None:
    declared = {
        component
        for entry in COVERAGE_MATRIX.values()
        for component in entry.active_components
    }
    assert declared <= set(BUILTIN_COMPONENT_CLASSES)
