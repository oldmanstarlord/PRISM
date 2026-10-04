"""Point-in-time input preparation for the correlation MST."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from backend.app.sector_divergence.inputs import (
    AdjustedCloseObservation,
    UniverseMember,
    load_latest_adjusted_closes,
    load_universe_members,
)

FORMULA_VERSION = "correlation-mst-v1"
LOOKBACK_RETURNS = 120
REQUIRED_PRICE_DATES = LOOKBACK_RETURNS + 1


@dataclass(frozen=True, slots=True)
class MstInputExclusion:
    security_id: UUID
    symbol: str
    reason: str
    details: str


@dataclass(frozen=True, slots=True)
class MstInputs:
    window_end: date
    data_cutoff: datetime
    adjusted_closes: pd.DataFrame
    adjustment_versions: pd.DataFrame
    adjustment_times: pd.DataFrame
    security_ids: Mapping[str, UUID]
    industries: Mapping[str, str]
    membership_sources: Mapping[str, str]
    exclusions: tuple[MstInputExclusion, ...]
    formula_version: str = FORMULA_VERSION


def prepare_inputs(
    members: list[UniverseMember],
    observations: list[AdjustedCloseObservation],
    window_end: date,
    data_cutoff: datetime,
) -> MstInputs:
    """Create an aligned, non-imputed adjusted-close panel for Layer 2."""
    if data_cutoff.tzinfo is None or data_cutoff.utcoffset() is None:
        raise ValueError("data_cutoff must be timezone-aware")

    member_by_id: dict[UUID, UniverseMember] = {}
    symbol_by_id: dict[UUID, str] = {}
    security_ids: dict[str, UUID] = {}
    industries: dict[str, str] = {}
    membership_sources: dict[str, str] = {}
    for member in members:
        security_id = member.security_id
        symbol = member.symbol
        if security_id in member_by_id or symbol in security_ids:
            raise ValueError("Duplicate universe member identity or symbol")
        member_by_id[security_id] = member
        symbol_by_id[security_id] = symbol
        security_ids[symbol] = security_id
        industry = member.industry
        industries[symbol] = industry.strip() if industry else "Unclassified"
        membership_sources[symbol] = member.membership_source

    seen: set[tuple[UUID, date]] = set()
    valid: list[AdjustedCloseObservation] = []
    invalid_symbols: set[str] = set()
    for observation in observations:
        if observation.security_id not in member_by_id:
            continue
        key = (observation.security_id, observation.trade_date)
        if key in seen:
            raise ValueError(f"Duplicate latest adjusted price for {key}")
        seen.add(key)
        if not observation.adjusted_close.is_finite() or observation.adjusted_close <= 0:
            invalid_symbols.add(symbol_by_id[observation.security_id])
            continue
        valid.append(observation)

    dates = sorted({item.trade_date for item in valid})[-REQUIRED_PRICE_DATES:]
    symbols = sorted(security_ids)
    index = pd.Index(dates, name="trade_date")
    closes = pd.DataFrame(index=index, columns=symbols, dtype="float64")
    versions = pd.DataFrame(index=index, columns=symbols, dtype="object")
    times = pd.DataFrame(index=index, columns=symbols, dtype="object")
    selected_dates = set(dates)
    for item in valid:
        if item.trade_date not in selected_dates:
            continue
        symbol = symbol_by_id[item.security_id]
        closes.at[item.trade_date, symbol] = float(item.adjusted_close)
        versions.at[item.trade_date, symbol] = item.adjustment_version
        times.at[item.trade_date, symbol] = item.computed_at

    exclusions = tuple(
        MstInputExclusion(
            security_id=security_ids[symbol],
            symbol=symbol,
            reason="invalid_adjusted_close",
            details="At least one non-positive or non-finite adjusted close was rejected",
        )
        for symbol in sorted(invalid_symbols)
    )
    return MstInputs(
        window_end=window_end,
        data_cutoff=data_cutoff,
        adjusted_closes=closes,
        adjustment_versions=versions,
        adjustment_times=times,
        security_ids=MappingProxyType(security_ids),
        industries=MappingProxyType(industries),
        membership_sources=MappingProxyType(membership_sources),
        exclusions=exclusions,
    )


def load_inputs(
    session: Session,
    window_end: date,
    lookback_start: date,
    data_cutoff: datetime,
) -> MstInputs:
    if lookback_start > window_end:
        raise ValueError("lookback_start must be on or before window_end")
    members = load_universe_members(session, window_end)
    if not members:
        raise ValueError("No observed NIFTY 200 membership exists for the requested window end")
    observations = load_latest_adjusted_closes(
        session,
        [member.security_id for member in members],
        lookback_start,
        window_end,
        data_cutoff,
    )
    return prepare_inputs(members, observations, window_end, data_cutoff)
