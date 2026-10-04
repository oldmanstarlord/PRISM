from datetime import UTC, date, datetime
from types import MappingProxyType
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
import pytest

from backend.app.sector_divergence.inputs import InputExclusion, SectorDivergenceInputs
from backend.app.sector_divergence.service import (
    build_company_comparison,
    calculation_configuration,
    input_fingerprint,
)

SECURITY_ID = UUID("00000000-0000-0000-0000-000000000001")
CUTOFF = datetime(2026, 10, 2, 12, tzinfo=UTC)


def make_inputs(price: float = 100.0) -> SectorDivergenceInputs:
    index = pd.Index([date(2026, 10, 1)], name="trade_date")
    return SectorDivergenceInputs(
        signal_date=date(2026, 10, 1),
        data_cutoff=CUTOFF,
        adjusted_closes=pd.DataFrame({"TEST": [price]}, index=index),
        adjustment_versions=pd.DataFrame(
            {"TEST": ["yfinance-adjclose-v1-r1"]}, index=index
        ),
        adjustment_times=pd.DataFrame({"TEST": [CUTOFF]}, index=index),
        security_ids=MappingProxyType({"TEST": SECURITY_ID}),
        industries=MappingProxyType({"TEST": "Test Industry"}),
        membership_sources=MappingProxyType({"TEST": "official.csv"}),
        exclusions=(
            InputExclusion(SECURITY_ID, "OLD", "test_reason", "test details"),
        ),
        issues=(),
    )


def test_input_fingerprint_is_deterministic_and_data_sensitive() -> None:
    assert input_fingerprint(make_inputs()) == input_fingerprint(make_inputs())
    assert input_fingerprint(make_inputs()) != input_fingerprint(make_inputs(101.0))


def test_configuration_records_all_approved_horizons() -> None:
    configuration = calculation_configuration()

    assert configuration["formula_version"] == "sector-divergence-v1"
    assert configuration["horizons"] == [1, 5, 20]
    assert configuration["minimum_industry_members"] == 5


def test_company_comparison_uses_leave_one_out_peer_median() -> None:
    dates = [timestamp.date() for timestamp in pd.bdate_range("2026-09-21", periods=4)]
    symbols = ["TARGET", "PEER1", "PEER2", "PEER3", "PEER4"]
    panel = pd.DataFrame(
        {
            "TARGET": [100.0, 120.0, 144.0, 172.8],
            "PEER1": [100.0, 101.0, 102.01, 103.0301],
            "PEER2": [100.0, 101.0, 102.01, 103.0301],
            "PEER3": [100.0, 101.0, 102.01, 103.0301],
            "PEER4": [100.0, 101.0, 102.01, 103.0301],
        },
        index=pd.Index(dates, name="trade_date"),
    )
    inputs = SectorDivergenceInputs(
        signal_date=dates[-1],
        data_cutoff=CUTOFF,
        adjusted_closes=panel,
        adjustment_versions=pd.DataFrame("v1", index=panel.index, columns=panel.columns),
        adjustment_times=pd.DataFrame(CUTOFF, index=panel.index, columns=panel.columns),
        security_ids=MappingProxyType(
            {symbol: UUID(int=index + 1) for index, symbol in enumerate(symbols)}
        ),
        industries=MappingProxyType({symbol: "Industry" for symbol in symbols}),
        membership_sources=MappingProxyType({symbol: "source" for symbol in symbols}),
        exclusions=(),
        issues=(),
    )

    comparison = build_company_comparison(inputs, "TARGET")

    assert comparison.peer_symbols == ("PEER1", "PEER2", "PEER3", "PEER4")
    assert len(comparison.points) == 3
    assert comparison.points[-1].stock_index == pytest.approx(144.0)
    assert comparison.points[-1].benchmark_index == pytest.approx(102.01)
