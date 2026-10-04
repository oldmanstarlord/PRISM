from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
import pytest

from backend.app.correlation_mst.inputs import prepare_inputs
from backend.app.sector_divergence.inputs import AdjustedCloseObservation, UniverseMember

CUTOFF = datetime(2026, 10, 4, 12, tzinfo=UTC)


def member(identifier: int, symbol: str) -> UniverseMember:
    return UniverseMember(UUID(int=identifier), symbol, "Industry", "official-snapshot")


def observation(identifier: int, trade_date: date, value: str) -> AdjustedCloseObservation:
    return AdjustedCloseObservation(
        UUID(int=identifier), trade_date, Decimal(value), "yfinance-adjclose-v1-r1", CUTOFF
    )


def test_inputs_keep_latest_121_dates_without_imputation() -> None:
    dates = [timestamp.date() for timestamp in pd.bdate_range("2026-01-01", periods=123)]
    observations = [observation(1, day, "100") for day in dates]
    observations += [observation(2, day, "200") for day in dates if day != dates[-2]]

    inputs = prepare_inputs(
        [member(1, "A"), member(2, "B")], observations, dates[-1], CUTOFF
    )

    assert len(inputs.adjusted_closes) == 121
    assert inputs.adjusted_closes.index[0] == dates[-121]
    assert inputs.adjusted_closes.index[-1] == dates[-1]
    assert pd.isna(inputs.adjusted_closes.at[dates[-2], "B"])


def test_inputs_reject_duplicate_latest_observations() -> None:
    day = date(2026, 10, 1)
    duplicate = observation(1, day, "100")

    with pytest.raises(ValueError, match="Duplicate latest adjusted price"):
        prepare_inputs([member(1, "A")], [duplicate, duplicate], day, CUTOFF)
