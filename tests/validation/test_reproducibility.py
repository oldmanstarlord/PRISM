from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from backend.app.correlation_mst.calculator import (
    MstCalculation,
    MstEdgeResult,
    MstNode,
)
from backend.app.validation.reproducibility import mst_digest


def test_mst_digest_ignores_calculation_wall_clock_time() -> None:
    node_a = MstNode(UUID(int=1), "A", "Industry", 120, "source")
    node_b = MstNode(UUID(int=2), "B", "Industry", 120, "source")
    edge = MstEdgeResult(UUID(int=1), UUID(int=2), "A", "B", 0.8, 0.632455532, 120, 1)
    calculation = MstCalculation(
        date(2026, 4, 1),
        date(2026, 10, 1),
        (node_a, node_b),
        (edge,),
        (),
        True,
        True,
        "correlation-mst-v1",
        datetime(2026, 10, 2, tzinfo=UTC),
    )

    later = replace(calculation, computed_at=calculation.computed_at + timedelta(days=1))

    assert mst_digest(calculation) == mst_digest(later)
