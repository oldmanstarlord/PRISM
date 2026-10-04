"""Point-in-time input preparation for deterministic sector divergence."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    PriceDailyAdjusted,
    Security,
    SecurityAlias,
    Universe,
    UniverseMembership,
)

FORMULA_VERSION = "sector-divergence-v1"
ADJUSTMENT_METHOD_PREFIX = "yfinance-adjclose-v1-r"
MINIMUM_PRICE_OBSERVATIONS = 46
MINIMUM_INDUSTRY_MEMBERS = 5


@dataclass(frozen=True, slots=True)
class UniverseMember:
    security_id: UUID
    symbol: str
    industry: str | None
    membership_source: str


@dataclass(frozen=True, slots=True)
class AdjustedCloseObservation:
    security_id: UUID
    trade_date: date
    adjusted_close: Decimal
    adjustment_version: str
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class InputExclusion:
    security_id: UUID
    symbol: str
    reason: str
    details: str


@dataclass(frozen=True, slots=True)
class InputIssue:
    security_id: UUID
    symbol: str
    trade_date: date
    reason: str


@dataclass(frozen=True, slots=True)
class SectorDivergenceInputs:
    signal_date: date
    data_cutoff: datetime
    adjusted_closes: pd.DataFrame
    adjustment_versions: pd.DataFrame
    adjustment_times: pd.DataFrame
    security_ids: Mapping[str, UUID]
    industries: Mapping[str, str]
    membership_sources: Mapping[str, str]
    exclusions: tuple[InputExclusion, ...]
    issues: tuple[InputIssue, ...]
    formula_version: str = FORMULA_VERSION


def load_universe_members(session: Session, signal_date: date) -> list[UniverseMember]:
    """Load the membership and active NSE symbol genuinely observed for a signal date."""
    rows = session.execute(
        select(
            Security.id,
            SecurityAlias.symbol,
            Security.industry,
            UniverseMembership.source,
        )
        .join(UniverseMembership, UniverseMembership.security_id == Security.id)
        .join(Universe, Universe.id == UniverseMembership.universe_id)
        .join(SecurityAlias, SecurityAlias.security_id == Security.id)
        .where(
            Universe.name == "NIFTY 200",
            UniverseMembership.valid_from <= signal_date,
            (UniverseMembership.valid_to.is_(None) | (UniverseMembership.valid_to >= signal_date)),
            SecurityAlias.exchange == "NSE",
            SecurityAlias.valid_from <= signal_date,
            (SecurityAlias.valid_to.is_(None) | (SecurityAlias.valid_to >= signal_date)),
        )
        .order_by(SecurityAlias.symbol, Security.id)
    ).all()
    return [
        UniverseMember(
            security_id=row.id,
            symbol=row.symbol,
            industry=row.industry,
            membership_source=row.source,
        )
        for row in rows
    ]


def load_latest_adjusted_closes(
    session: Session,
    security_ids: list[UUID],
    start_date: date,
    end_date: date,
    data_cutoff: datetime,
) -> list[AdjustedCloseObservation]:
    """Select one latest adjustment revision per security/date available by the cutoff."""
    if not security_ids:
        return []
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if data_cutoff.tzinfo is None or data_cutoff.utcoffset() is None:
        raise ValueError("data_cutoff must be timezone-aware")

    revision_number = cast(
        func.replace(PriceDailyAdjusted.method_version, ADJUSTMENT_METHOD_PREFIX, ""),
        Integer,
    )
    ranked = (
        select(
            PriceDailyAdjusted.security_id.label("security_id"),
            PriceDailyAdjusted.trade_date.label("trade_date"),
            PriceDailyAdjusted.adjusted_close.label("adjusted_close"),
            PriceDailyAdjusted.method_version.label("adjustment_version"),
            PriceDailyAdjusted.computed_at.label("computed_at"),
            func.row_number()
            .over(
                partition_by=(
                    PriceDailyAdjusted.security_id,
                    PriceDailyAdjusted.trade_date,
                ),
                order_by=(
                    PriceDailyAdjusted.computed_at.desc(),
                    revision_number.desc(),
                    PriceDailyAdjusted.id.desc(),
                ),
            )
            .label("revision_rank"),
        )
        .where(
            PriceDailyAdjusted.security_id.in_(security_ids),
            PriceDailyAdjusted.trade_date >= start_date,
            PriceDailyAdjusted.trade_date <= end_date,
            PriceDailyAdjusted.computed_at <= data_cutoff,
            PriceDailyAdjusted.method_version.like(f"{ADJUSTMENT_METHOD_PREFIX}%"),
        )
        .subquery()
    )
    rows = session.execute(
        select(
            ranked.c.security_id,
            ranked.c.trade_date,
            ranked.c.adjusted_close,
            ranked.c.adjustment_version,
            ranked.c.computed_at,
        )
        .where(ranked.c.revision_rank == 1)
        .order_by(ranked.c.trade_date, ranked.c.security_id)
    ).all()
    return [
        AdjustedCloseObservation(
            security_id=row.security_id,
            trade_date=row.trade_date,
            adjusted_close=row.adjusted_close,
            adjustment_version=row.adjustment_version,
            computed_at=row.computed_at,
        )
        for row in rows
    ]


def prepare_inputs(
    members: list[UniverseMember],
    observations: list[AdjustedCloseObservation],
    signal_date: date,
    data_cutoff: datetime,
    minimum_price_observations: int = MINIMUM_PRICE_OBSERVATIONS,
    minimum_industry_members: int = MINIMUM_INDUSTRY_MEMBERS,
) -> SectorDivergenceInputs:
    """Build aligned, non-imputed input panels with explicit eligibility decisions."""
    if minimum_price_observations < 2:
        raise ValueError("minimum_price_observations must be at least 2")
    if minimum_industry_members < 2:
        raise ValueError("minimum_industry_members must be at least 2")
    if data_cutoff.tzinfo is None or data_cutoff.utcoffset() is None:
        raise ValueError("data_cutoff must be timezone-aware")

    member_by_id: dict[UUID, UniverseMember] = {}
    symbols: set[str] = set()
    for member in members:
        if member.security_id in member_by_id:
            raise ValueError(f"Duplicate universe member security_id: {member.security_id}")
        if member.symbol in symbols:
            raise ValueError(f"Duplicate active universe symbol: {member.symbol}")
        member_by_id[member.security_id] = member
        symbols.add(member.symbol)

    valid_observations: dict[UUID, list[AdjustedCloseObservation]] = {
        member.security_id: [] for member in members
    }
    seen_keys: set[tuple[UUID, date]] = set()
    issues: list[InputIssue] = []
    for observation in observations:
        observed_member = member_by_id.get(observation.security_id)
        if observed_member is None:
            continue
        key = (observation.security_id, observation.trade_date)
        if key in seen_keys:
            raise ValueError(
                "Multiple latest adjusted prices for "
                f"{observed_member.symbol} on {observation.trade_date}"
            )
        seen_keys.add(key)
        if (
            not observation.adjusted_close.is_finite()
            or observation.adjusted_close <= 0
        ):
            issues.append(
                InputIssue(
                    security_id=observed_member.security_id,
                    symbol=observed_member.symbol,
                    trade_date=observation.trade_date,
                    reason="invalid_adjusted_close",
                )
            )
            continue
        valid_observations[observation.security_id].append(observation)

    exclusions: list[InputExclusion] = []
    candidates: list[UniverseMember] = []
    for member in sorted(members, key=lambda item: (item.symbol, str(item.security_id))):
        industry = member.industry.strip() if member.industry else ""
        observation_count = len(valid_observations[member.security_id])
        if not industry:
            exclusions.append(
                InputExclusion(
                    member.security_id,
                    member.symbol,
                    "missing_industry",
                    "Official NIFTY 200 Industry value is absent",
                )
            )
        elif observation_count < minimum_price_observations:
            exclusions.append(
                InputExclusion(
                    member.security_id,
                    member.symbol,
                    "insufficient_price_observations",
                    f"Required {minimum_price_observations}; found {observation_count}",
                )
            )
        else:
            candidates.append(member)

    industry_counts: dict[str, int] = {}
    for member in candidates:
        assert member.industry is not None
        industry = member.industry.strip()
        industry_counts[industry] = industry_counts.get(industry, 0) + 1

    eligible: list[UniverseMember] = []
    for member in candidates:
        assert member.industry is not None
        industry = member.industry.strip()
        group_size = industry_counts[industry]
        if group_size < minimum_industry_members:
            exclusions.append(
                InputExclusion(
                    member.security_id,
                    member.symbol,
                    "insufficient_industry_members",
                    f"Required {minimum_industry_members}; found {group_size} in {industry}",
                )
            )
        else:
            eligible.append(member)

    eligible.sort(key=lambda item: (item.symbol, str(item.security_id)))
    eligible_ids = {member.security_id for member in eligible}
    eligible_observations = [
        observation
        for observation in observations
        if observation.security_id in eligible_ids
        and observation.adjusted_close.is_finite()
        and observation.adjusted_close > 0
    ]
    ordered_dates = sorted({observation.trade_date for observation in eligible_observations})
    ordered_symbols = [member.symbol for member in eligible]
    panel_index = pd.Index(ordered_dates, name="trade_date")

    adjusted_closes = pd.DataFrame(
        index=panel_index,
        columns=ordered_symbols,
        dtype="float64",
    )
    adjustment_versions = pd.DataFrame(index=panel_index, columns=ordered_symbols, dtype="object")
    adjustment_times = pd.DataFrame(index=panel_index, columns=ordered_symbols, dtype="object")
    symbol_by_id = {member.security_id: member.symbol for member in eligible}
    for observation in eligible_observations:
        symbol = symbol_by_id[observation.security_id]
        adjusted_closes.at[observation.trade_date, symbol] = float(observation.adjusted_close)
        adjustment_versions.at[observation.trade_date, symbol] = observation.adjustment_version
        adjustment_times.at[observation.trade_date, symbol] = observation.computed_at

    return SectorDivergenceInputs(
        signal_date=signal_date,
        data_cutoff=data_cutoff,
        adjusted_closes=adjusted_closes,
        adjustment_versions=adjustment_versions,
        adjustment_times=adjustment_times,
        security_ids=MappingProxyType(
            {member.symbol: member.security_id for member in eligible}
        ),
        industries=MappingProxyType(
            {member.symbol: member.industry.strip() for member in eligible if member.industry}
        ),
        membership_sources=MappingProxyType(
            {member.symbol: member.membership_source for member in eligible}
        ),
        exclusions=tuple(exclusions),
        issues=tuple(sorted(issues, key=lambda item: (item.trade_date, item.symbol))),
    )


def load_inputs(
    session: Session,
    signal_date: date,
    lookback_start: date,
    data_cutoff: datetime,
    minimum_price_observations: int = MINIMUM_PRICE_OBSERVATIONS,
    minimum_industry_members: int = MINIMUM_INDUSTRY_MEMBERS,
) -> SectorDivergenceInputs:
    """Load and prepare the approved version 1 input envelope from PostgreSQL."""
    if lookback_start > signal_date:
        raise ValueError("lookback_start must be on or before signal_date")
    members = load_universe_members(session, signal_date)
    if not members:
        raise ValueError(
            "No observed NIFTY 200 membership exists for the requested signal date; "
            "PRISM must not invent historical membership"
        )
    observations = load_latest_adjusted_closes(
        session,
        [member.security_id for member in members],
        lookback_start,
        signal_date,
        data_cutoff,
    )
    return prepare_inputs(
        members,
        observations,
        signal_date,
        data_cutoff,
        minimum_price_observations,
        minimum_industry_members,
    )
