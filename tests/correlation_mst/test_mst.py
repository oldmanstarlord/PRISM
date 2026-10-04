from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest

from backend.app.correlation_mst.calculator import calculate_mst
from backend.app.correlation_mst.inputs import MstInputs

COMPUTED_AT = datetime(2026, 10, 4, 12, tzinfo=UTC)


def make_inputs(*, include_sparse: bool = False, include_future: bool = False) -> MstInputs:
    periods = 122 if include_future else 121
    dates = [timestamp.date() for timestamp in pd.bdate_range("2026-01-01", periods=periods)]
    signal_date = dates[120]
    base_returns = np.array([0.002 * np.sin(index / 5) + 0.0003 for index in range(120)])
    symbols = ["A", "B", "C", "D"]
    return_map = {
        "A": base_returns,
        "B": base_returns,
        "C": base_returns,
        "D": base_returns,
    }
    prices: dict[str, list[float]] = {}
    for symbol in symbols:
        values = [100.0]
        for value in return_map[symbol]:
            values.append(values[-1] * np.exp(value))
        if include_future:
            values.append(values[-1] * (10.0 if symbol == "A" else 0.1))
        prices[symbol] = values
    if include_sparse:
        symbols.append("E")
        prices["E"] = [100.0] * periods
        prices["E"][:70] = [float("nan")] * 70
    panel = pd.DataFrame(prices, index=pd.Index(dates, name="trade_date"))
    return MstInputs(
        window_end=signal_date,
        data_cutoff=COMPUTED_AT,
        adjusted_closes=panel,
        adjustment_versions=pd.DataFrame("v1", index=panel.index, columns=panel.columns),
        adjustment_times=pd.DataFrame(COMPUTED_AT, index=panel.index, columns=panel.columns),
        security_ids=MappingProxyType(
            {symbol: UUID(int=index + 1) for index, symbol in enumerate(symbols)}
        ),
        industries=MappingProxyType({symbol: "Industry" for symbol in symbols}),
        membership_sources=MappingProxyType({symbol: "source" for symbol in symbols}),
        exclusions=(),
    )


def test_mst_is_connected_acyclic_n_minus_one_and_deterministic() -> None:
    calculation = calculate_mst(make_inputs(), computed_at=COMPUTED_AT)

    assert calculation.is_connected is True
    assert calculation.is_acyclic is True
    assert len(calculation.nodes) == 4
    assert len(calculation.edges) == 3
    assert [(edge.symbol_a, edge.symbol_b) for edge in calculation.edges] == [
        ("A", "B"),
        ("A", "C"),
        ("A", "D"),
    ]
    assert all(edge.correlation == pytest.approx(1.0) for edge in calculation.edges)
    assert all(edge.distance == pytest.approx(0.0) for edge in calculation.edges)


def test_sparse_security_is_explicitly_excluded() -> None:
    calculation = calculate_mst(make_inputs(include_sparse=True), computed_at=COMPUTED_AT)

    exclusion = next(item for item in calculation.exclusions if item.symbol == "E")
    assert exclusion.reason == "insufficient_return_observations"
    assert len(calculation.nodes) == 4


def test_future_prices_do_not_change_window_end_tree() -> None:
    without_future = calculate_mst(make_inputs(), computed_at=COMPUTED_AT)
    with_future = calculate_mst(make_inputs(include_future=True), computed_at=COMPUTED_AT)

    assert with_future.edges == without_future.edges
