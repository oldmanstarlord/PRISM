"""Persistence and read services for reproducible sector-divergence runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from math import exp
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    PriceDailyAdjusted,
    SectorDivergenceIssue,
    SectorDivergenceRun,
    SectorDivergenceScore,
)
from backend.app.sector_divergence.calculator import (
    ESTIMATION_WINDOW,
    HORIZONS,
    MINIMUM_CONTEMPORANEOUS_PEERS,
    MINIMUM_PAIRED_OBSERVATIONS,
    calculate_sector_divergence,
)
from backend.app.sector_divergence.inputs import (
    FORMULA_VERSION,
    MINIMUM_INDUSTRY_MEMBERS,
    MINIMUM_PRICE_OBSERVATIONS,
    SectorDivergenceInputs,
    load_inputs,
)


@dataclass(frozen=True, slots=True)
class PersistedCalculation:
    run_id: UUID
    created: bool
    score_count: int
    issue_count: int
    exclusion_count: int


@dataclass(frozen=True, slots=True)
class ComparisonPoint:
    trade_date: date
    stock_index: float
    benchmark_index: float


@dataclass(frozen=True, slots=True)
class CompanyComparison:
    symbol: str
    industry: str
    peer_symbols: tuple[str, ...]
    points: tuple[ComparisonPoint, ...]
    omitted_observations: int


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def calculation_configuration() -> dict[str, object]:
    return {
        "formula_version": FORMULA_VERSION,
        "estimation_window": ESTIMATION_WINDOW,
        "minimum_paired_observations": MINIMUM_PAIRED_OBSERVATIONS,
        "minimum_contemporaneous_peers": MINIMUM_CONTEMPORANEOUS_PEERS,
        "minimum_price_observations": MINIMUM_PRICE_OBSERVATIONS,
        "minimum_industry_members": MINIMUM_INDUSTRY_MEMBERS,
        "horizons": list(HORIZONS),
    }


def input_fingerprint(inputs: SectorDivergenceInputs) -> str:
    """Hash the selected point-in-time inputs and eligibility decisions."""
    observations: list[list[object]] = []
    for trade_date, row in inputs.adjusted_closes.sort_index().iterrows():
        for symbol in sorted(inputs.security_ids):
            value = row[symbol]
            if value == value:  # NaN is deliberately represented as missing.
                observations.append(
                    [
                        trade_date.isoformat(),
                        symbol,
                        format(float(value), ".15g"),
                        str(inputs.adjustment_versions.at[trade_date, symbol]),
                        str(inputs.adjustment_times.at[trade_date, symbol]),
                    ]
                )
    envelope = {
        "signal_date": inputs.signal_date.isoformat(),
        "data_cutoff": inputs.data_cutoff.isoformat(),
        "members": [
            [symbol, str(inputs.security_ids[symbol]), inputs.industries[symbol],
             inputs.membership_sources[symbol]]
            for symbol in sorted(inputs.security_ids)
        ],
        "observations": observations,
        "exclusions": [
            [str(item.security_id), item.symbol, item.reason, item.details]
            for item in inputs.exclusions
        ],
    }
    return _canonical_hash(envelope)


def build_company_comparison(
    inputs: SectorDivergenceInputs,
    symbol: str,
    *,
    maximum_points: int = 61,
) -> CompanyComparison:
    """Build an indexed stock/leave-one-out benchmark series from Layer 1 inputs."""
    if maximum_points < 2:
        raise ValueError("maximum_points must be at least 2")
    if symbol not in inputs.security_ids:
        raise ValueError(f"{symbol} is not eligible in this Layer 1 run")

    industry = inputs.industries[symbol]
    peer_symbols = tuple(
        candidate
        for candidate in sorted(inputs.security_ids)
        if candidate != symbol and inputs.industries[candidate] == industry
    )
    if len(peer_symbols) < MINIMUM_CONTEMPORANEOUS_PEERS:
        raise ValueError(f"{symbol} has insufficient eligible industry peers")

    prices = inputs.adjusted_closes.sort_index().loc[: inputs.signal_date]
    log_returns = np.log(prices.astype("float64")).diff()
    peer_returns = log_returns[list(peer_symbols)]
    benchmark = peer_returns.median(axis=1, skipna=True).where(
        peer_returns.notna().sum(axis=1) >= MINIMUM_CONTEMPORANEOUS_PEERS
    )
    paired = (
        log_returns[symbol]
        .rename("stock")
        .to_frame()
        .assign(benchmark=benchmark)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    total_paired = len(paired)
    paired = paired.tail(maximum_points)
    if len(paired) < 2:
        raise ValueError(f"{symbol} has insufficient paired observations for a comparison chart")

    stock_level = 100.0
    benchmark_level = 100.0
    points = [
        ComparisonPoint(
            trade_date=paired.index[0],
            stock_index=stock_level,
            benchmark_index=benchmark_level,
        )
    ]
    for trade_date, row in paired.iloc[1:].iterrows():
        stock_level *= exp(float(row["stock"]))
        benchmark_level *= exp(float(row["benchmark"]))
        points.append(
            ComparisonPoint(
                trade_date=trade_date,
                stock_index=stock_level,
                benchmark_index=benchmark_level,
            )
        )
    return CompanyComparison(
        symbol=symbol,
        industry=industry,
        peer_symbols=peer_symbols,
        points=tuple(points),
        omitted_observations=max(0, total_paired - len(paired)),
    )


def persist_calculation(
    session: Session,
    *,
    signal_date: date,
    lookback_start: date,
    data_cutoff: datetime,
    computed_at: datetime | None = None,
) -> PersistedCalculation:
    """Calculate and atomically persist a run, returning an existing identical run if present."""
    inputs = load_inputs(session, signal_date, lookback_start, data_cutoff)
    configuration = calculation_configuration()
    configuration_hash = _canonical_hash(configuration)
    fingerprint = input_fingerprint(inputs)
    existing = session.scalar(
        select(SectorDivergenceRun).where(
            SectorDivergenceRun.signal_date == signal_date,
            SectorDivergenceRun.implementation_version == FORMULA_VERSION,
            SectorDivergenceRun.configuration_hash == configuration_hash,
            SectorDivergenceRun.input_fingerprint == fingerprint,
            SectorDivergenceRun.status == "completed",
        )
    )
    if existing is not None:
        return PersistedCalculation(
            existing.id,
            False,
            existing.score_count,
            existing.issue_count,
            existing.exclusion_count,
        )

    calculation_time = computed_at or datetime.now(UTC)
    calculation = calculate_sector_divergence(inputs, computed_at=calculation_time)
    run = SectorDivergenceRun(
        signal_date=signal_date,
        data_cutoff=data_cutoff,
        lookback_start=lookback_start,
        implementation_version=FORMULA_VERSION,
        configuration=configuration,
        configuration_hash=configuration_hash,
        input_fingerprint=fingerprint,
        status="completed",
        score_count=len(calculation.scores),
        issue_count=len(calculation.issues) + len(inputs.issues),
        exclusion_count=len(calculation.input_exclusions),
        started_at=calculation_time,
        completed_at=calculation_time,
    )
    session.add(run)
    session.flush()
    session.add_all(
        [
            SectorDivergenceScore(
                run_id=run.id,
                security_id=item.security_id,
                symbol=item.symbol,
                industry=item.industry,
                horizon=item.horizon,
                residual_value=Decimal(str(item.residual_value)),
                divergence_value=Decimal(str(item.divergence_value)),
                alpha=Decimal(str(item.alpha)),
                beta=Decimal(str(item.beta)),
                residual_volatility=Decimal(str(item.residual_volatility)),
                industry_percentile=Decimal(str(item.industry_percentile)),
                interpretation=item.interpretation,
                lookback_start=item.lookback_start,
                lookback_end=item.lookback_end,
                observations_used=item.observations_used,
                membership_source=item.membership_source,
                adjustment_version=item.adjustment_version,
                computed_at=item.computed_at,
            )
            for item in calculation.scores
        ]
    )
    session.add_all(
        [
            SectorDivergenceIssue(
                run_id=run.id,
                security_id=item.security_id,
                symbol=item.symbol,
                stage="calculation",
                horizon=item.horizon,
                reason=item.reason,
                details=item.details,
            )
            for item in calculation.issues
        ]
        + [
            SectorDivergenceIssue(
                run_id=run.id,
                security_id=item.security_id,
                symbol=item.symbol,
                stage="input",
                horizon=None,
                reason=item.reason,
                details=f"Invalid observation on {item.trade_date.isoformat()}",
            )
            for item in inputs.issues
        ]
        + [
            SectorDivergenceIssue(
                run_id=run.id,
                security_id=item.security_id,
                symbol=item.symbol,
                stage="exclusion",
                horizon=None,
                reason=item.reason,
                details=item.details,
            )
            for item in calculation.input_exclusions
        ]
    )
    session.commit()
    return PersistedCalculation(
        run.id,
        True,
        run.score_count,
        run.issue_count,
        run.exclusion_count,
    )


def latest_market_snapshot(session: Session) -> tuple[date, datetime]:
    signal_date = session.scalar(select(func.max(PriceDailyAdjusted.trade_date)))
    if signal_date is None:
        raise ValueError("No adjusted daily prices are available")
    cutoff = session.scalar(
        select(func.max(PriceDailyAdjusted.computed_at)).where(
            PriceDailyAdjusted.trade_date <= signal_date
        )
    )
    if cutoff is None:
        raise ValueError("No adjusted-price computation timestamp is available")
    return signal_date, cutoff


def latest_completed_run_query() -> Select[SectorDivergenceRun]:
    return (
        select(SectorDivergenceRun)
        .where(SectorDivergenceRun.status == "completed")
        .order_by(desc(SectorDivergenceRun.signal_date), desc(SectorDivergenceRun.completed_at))
        .limit(1)
    )


def run_summary(run: SectorDivergenceRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "signal_date": run.signal_date,
        "data_cutoff": run.data_cutoff,
        "lookback_start": run.lookback_start,
        "implementation_version": run.implementation_version,
        "configuration": run.configuration,
        "status": run.status,
        "score_count": run.score_count,
        "issue_count": run.issue_count,
        "exclusion_count": run.exclusion_count,
        "completed_at": run.completed_at,
    }
