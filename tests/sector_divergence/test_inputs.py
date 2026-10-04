from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pandas as pd
import pytest

from backend.app.sector_divergence.inputs import (
    AdjustedCloseObservation,
    UniverseMember,
    prepare_inputs,
)

DATA_CUTOFF = datetime(2026, 10, 2, 12, tzinfo=UTC)
MEMBERSHIP_SOURCE = "official-test-snapshot"


def member(number: int, industry: str | None = "Banks") -> UniverseMember:
    return UniverseMember(
        security_id=UUID(int=number),
        symbol=f"STOCK{number}",
        industry=industry,
        membership_source=MEMBERSHIP_SOURCE,
    )


def observation(number: int, day: int, close: str = "100") -> AdjustedCloseObservation:
    return AdjustedCloseObservation(
        security_id=UUID(int=number),
        trade_date=date(2026, 9, day),
        adjusted_close=Decimal(close),
        adjustment_version="yfinance-adjclose-v1-r1",
        computed_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


def test_prepare_inputs_aligns_without_imputation_and_preserves_provenance() -> None:
    members = [member(number) for number in range(1, 6)]
    observations = [
        observation(number, day, str(100 + number + day))
        for number in range(1, 6)
        for day in (29, 30)
    ]

    result = prepare_inputs(
        members,
        list(reversed(observations)),
        signal_date=date(2026, 9, 30),
        data_cutoff=DATA_CUTOFF,
        minimum_price_observations=1 + 1,
        minimum_industry_members=5,
    )

    assert list(result.adjusted_closes.columns) == [
        "STOCK1",
        "STOCK2",
        "STOCK3",
        "STOCK4",
        "STOCK5",
    ]
    assert list(result.adjusted_closes.index) == [date(2026, 9, 29), date(2026, 9, 30)]
    assert result.adjustment_versions.at[date(2026, 9, 30), "STOCK1"] == (
        "yfinance-adjclose-v1-r1"
    )
    assert result.membership_sources["STOCK1"] == MEMBERSHIP_SOURCE
    assert result.exclusions == ()


def test_prepare_inputs_keeps_missing_cells_as_nan() -> None:
    members = [member(number) for number in range(1, 6)]
    observations = [
        observation(number, day)
        for number in range(1, 6)
        for day in (28, 29, 30)
        if not (number == 5 and day == 29)
    ]

    result = prepare_inputs(
        members,
        observations,
        signal_date=date(2026, 9, 30),
        data_cutoff=DATA_CUTOFF,
        minimum_price_observations=2,
    )

    assert pd.isna(result.adjusted_closes.at[date(2026, 9, 29), "STOCK5"])


def test_prepare_inputs_excludes_an_undersized_industry() -> None:
    members = [member(number, "Banks") for number in range(1, 5)]
    observations = [observation(number, day) for number in range(1, 5) for day in (29, 30)]

    result = prepare_inputs(
        members,
        observations,
        signal_date=date(2026, 9, 30),
        data_cutoff=DATA_CUTOFF,
        minimum_price_observations=2,
        minimum_industry_members=5,
    )

    assert result.adjusted_closes.empty
    assert len(result.exclusions) == 4
    assert {item.reason for item in result.exclusions} == {"insufficient_industry_members"}


def test_prepare_inputs_reports_invalid_prices_and_missing_industry() -> None:
    members = [member(1, None), *[member(number) for number in range(2, 7)]]
    observations = [
        observation(number, day)
        for number in range(1, 7)
        for day in (29, 30)
    ]
    observations[-1] = observation(6, 30, "NaN")

    result = prepare_inputs(
        members,
        observations,
        signal_date=date(2026, 9, 30),
        data_cutoff=DATA_CUTOFF,
        minimum_price_observations=2,
        minimum_industry_members=5,
    )

    assert any(
        item.symbol == "STOCK1" and item.reason == "missing_industry"
        for item in result.exclusions
    )
    assert any(
        item.symbol == "STOCK6" and item.reason == "invalid_adjusted_close"
        for item in result.issues
    )


def test_prepare_inputs_rejects_duplicate_latest_prices() -> None:
    members = [member(number) for number in range(1, 6)]
    duplicate = observation(1, 30)

    with pytest.raises(ValueError, match="Multiple latest adjusted prices"):
        prepare_inputs(
            members,
            [duplicate, duplicate],
            signal_date=date(2026, 9, 30),
            data_cutoff=DATA_CUTOFF,
            minimum_price_observations=2,
        )


def test_prepare_inputs_requires_timezone_aware_cutoff() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        prepare_inputs(
            [],
            [],
            signal_date=date(2026, 9, 30),
            data_cutoff=datetime(2026, 10, 2),
        )
