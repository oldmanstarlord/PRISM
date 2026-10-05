from datetime import date, timedelta

import pandas as pd
import pytest

from backend.app.portfolio_analytics.calculator import (
    MstEdgeData,
    calculate_mst_diagnostics,
    calculate_risk,
    calculate_stress,
)
from backend.app.portfolio_analytics.schemas import StressScenarioInput


def _price_frame() -> pd.DataFrame:
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=index) for index in range(6)]
    return pd.DataFrame(
        {
            "A": [100.0, 102.0, 101.0, 105.0, 104.0, 108.0],
            "B": [100.0, 101.0, 99.0, 100.0, 98.0, 102.0],
        },
        index=dates,
    )


def test_risk_metrics_and_euler_contributions_are_coherent() -> None:
    result = calculate_risk(
        prices=_price_frame(),
        weights_by_symbol={"A": 0.6, "B": 0.4},
        industries={"A": "Technology", "B": "Financials"},
        divergence={"A": (2.1, "strong")},
    )

    assert result.performance.total_return > 0
    assert result.performance.annualized_volatility > 0
    assert len(result.performance.points) == 6
    assert sum(item.risk_contribution for item in result.holdings) == pytest.approx(1.0)
    assert result.concentration.holding_hhi == pytest.approx(0.52)
    assert result.concentration.effective_holdings == pytest.approx(1 / 0.52, rel=1e-4)
    assert result.holdings[0].divergence_20d == pytest.approx(2.1)
    assert 1.0 <= result.diversification.effective_bets_risk <= 2.0


def test_mst_diagnostics_include_indirect_paths_bridges_and_clusters() -> None:
    edges = [
        MstEdgeData("A", "X", 0.8, 0.6),
        MstEdgeData("X", "B", 0.7, 0.7),
        MstEdgeData("B", "C", 0.4, 1.0),
    ]
    result = calculate_mst_diagnostics(
        run_id="run-1",
        as_of=date(2026, 10, 1),
        all_symbols={"A", "B", "C", "X"},
        edges=edges,
        holdings={"A": 0.5, "B": 0.25, "C": 0.25},
    )

    assert [(edge.symbol_a, edge.symbol_b) for edge in result.direct_edges] == [("B", "C")]
    path = next(
        item for item in result.holding_paths if item.symbol_a == "A" and item.symbol_b == "B"
    )
    assert path.path == ["A", "X", "B"]
    assert path.positive_path_product == pytest.approx(0.56)
    assert result.bridge_stocks[0].symbol == "X"
    assert result.bridge_stocks[0].path_pair_count == 2
    assert result.clusters[0].weight == pytest.approx(0.75)
    assert result.clusters[0].holding_symbols == ["A", "B"]


def test_stock_and_industry_stress_are_explicit_and_weighted() -> None:
    risk = calculate_risk(
        prices=_price_frame(),
        weights_by_symbol={"A": 0.6, "B": 0.4},
        industries={"A": "Technology", "B": "Financials"},
        divergence={},
    )
    stock = calculate_stress(
        StressScenarioInput(kind="stock", target="A", shock_percent=-10.0),
        risk.returns,
        {"A": 0.6, "B": 0.4},
        {"A": "Technology", "B": "Financials"},
    )
    assert stock is not None
    shocked = next(item for item in stock.results if item.symbol == "A")
    assert shocked.estimated_return_percent == pytest.approx(-10.0)
    assert shocked.portfolio_contribution_percent == pytest.approx(-6.0)

    industry = calculate_stress(
        StressScenarioInput(kind="industry", target="Technology", shock_percent=-10.0),
        risk.returns,
        {"A": 0.6, "B": 0.4},
        {"A": "Technology", "B": "Financials"},
    )
    assert industry is not None
    assert industry.portfolio_impact_percent == pytest.approx(-6.0)
    unaffected = next(item for item in industry.results if item.symbol == "B")
    assert unaffected.estimated_return_percent == 0.0
