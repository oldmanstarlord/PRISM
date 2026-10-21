"""Point-in-time ML inputs sourced exclusively from the validated Step 1 database."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    DataCoverageRun,
    DataQualityResult,
    PriceDailyAdjusted,
    PriceDailyRaw,
    Security,
    SecurityAlias,
)
from backend.app.market_data.metrics import METHODOLOGY_VERSION as SOURCE_METHODOLOGY_VERSION
from backend.app.market_data.service import active_nifty200_instruments


@dataclass(frozen=True, slots=True)
class ValidatedMarketData:
    prices: pd.DataFrame
    volumes: pd.DataFrame
    benchmark_prices: pd.Series
    eligible_security_ids: dict[str, UUID]
    universe_security_ids: dict[str, UUID]
    sectors: dict[str, str | None]
    excluded_reasons: dict[str, str]
    data_cutoff: date
    source_data_version: str
    quality_run_id: UUID


def _adjusted_series(session: Session, security_id: UUID, cutoff: date) -> pd.Series:
    rows = session.scalars(
        select(PriceDailyAdjusted)
        .where(
            PriceDailyAdjusted.security_id == security_id,
            PriceDailyAdjusted.trade_date <= cutoff,
        )
        .order_by(PriceDailyAdjusted.trade_date, PriceDailyAdjusted.computed_at.desc())
    ).all()
    latest: dict[date, float] = {}
    for row in rows:
        latest.setdefault(row.trade_date, float(row.adjusted_close))
    return pd.Series(latest, dtype=float).sort_index()


def _volume_series(session: Session, security_id: UUID, cutoff: date) -> pd.Series:
    rows = session.scalars(
        select(PriceDailyRaw)
        .where(
            PriceDailyRaw.security_id == security_id,
            PriceDailyRaw.trade_date <= cutoff,
            PriceDailyRaw.source == "yfinance",
        )
        .order_by(PriceDailyRaw.trade_date, PriceDailyRaw.source_revision.desc())
    ).all()
    latest: dict[date, float] = {}
    for row in rows:
        latest.setdefault(row.trade_date, float(row.volume))
    return pd.Series(latest, dtype=float).sort_index()


def load_validated_market_data(
    session: Session, *, cutoff: date | None = None
) -> ValidatedMarketData:
    coverage = session.scalar(
        select(DataCoverageRun).order_by(desc(DataCoverageRun.last_update_time)).limit(1)
    )
    if coverage is None or coverage.data_date is None:
        raise RuntimeError("No completed Step 1 coverage run is available")
    effective_cutoff = min(cutoff, coverage.data_date) if cutoff else coverage.data_date
    instruments = active_nifty200_instruments(session, effective_cutoff)
    if len(instruments) != 200:
        raise RuntimeError(f"Step 1 universe has {len(instruments)} members, expected 200")

    quality_rows = session.scalars(
        select(DataQualityResult).where(DataQualityResult.run_id == coverage.run_id)
    ).all()
    quality = {row.security_id: row for row in quality_rows}
    aliases = session.scalars(
        select(SecurityAlias).where(
            SecurityAlias.security_id.in_([item.security_id for item in instruments]),
            SecurityAlias.valid_to.is_(None),
        )
    ).all()
    verified = {
        alias.security_id
        for alias in aliases
        if alias.verification_status == "verified"
    }

    price_series: dict[str, pd.Series] = {}
    volume_series: dict[str, pd.Series] = {}
    security_ids: dict[str, UUID] = {}
    universe_security_ids = {
        instrument.symbol: instrument.security_id for instrument in instruments
    }
    security_rows = session.execute(
        select(Security.id, Security.sector).where(
            Security.id.in_(list(universe_security_ids.values()))
        )
    ).all()
    sector_by_id = {row.id: row.sector for row in security_rows}
    sectors = {
        symbol: sector_by_id.get(security_id)
        for symbol, security_id in universe_security_ids.items()
    }
    excluded: dict[str, str] = {}
    for instrument in instruments:
        quality_row = quality.get(instrument.security_id)
        if instrument.security_id not in verified:
            excluded[instrument.symbol] = "ticker_not_verified"
            continue
        if quality_row is None:
            excluded[instrument.symbol] = "quality_not_evaluated"
            continue
        if quality_row.status == "fail":
            codes = quality_row.reasons.get("codes", [])
            excluded[instrument.symbol] = "quality_failed: " + ",".join(map(str, codes))
            continue
        series = _adjusted_series(session, instrument.security_id, effective_cutoff)
        if series.empty:
            excluded[instrument.symbol] = "adjusted_prices_missing"
            continue
        price_series[instrument.symbol] = series
        volume_series[instrument.symbol] = _volume_series(
            session, instrument.security_id, effective_cutoff
        )
        security_ids[instrument.symbol] = instrument.security_id

    benchmark_alias = session.scalar(
        select(SecurityAlias).where(
            SecurityAlias.symbol == "^NSEI",
            SecurityAlias.valid_to.is_(None),
        )
    )
    if benchmark_alias is None or benchmark_alias.verification_status != "verified":
        raise RuntimeError("Verified ^NSEI benchmark history is unavailable")
    benchmark = _adjusted_series(session, benchmark_alias.security_id, effective_cutoff)
    if benchmark.empty:
        raise RuntimeError("Verified ^NSEI benchmark contains no adjusted prices")

    prices = pd.DataFrame(price_series).sort_index()
    volumes = pd.DataFrame(volume_series).sort_index()
    source_version = (
        f"coverage:{coverage.run_id};prices:yfinance-adjclose-v1;"
        f"metrics:{SOURCE_METHODOLOGY_VERSION}"
    )
    return ValidatedMarketData(
        prices=prices,
        volumes=volumes,
        benchmark_prices=benchmark,
        eligible_security_ids=security_ids,
        universe_security_ids=universe_security_ids,
        sectors=sectors,
        excluded_reasons=excluded,
        data_cutoff=effective_cutoff,
        source_data_version=source_version,
        quality_run_id=coverage.run_id,
    )


def cutoff_datetime(value: date) -> datetime:
    return datetime.combine(value, datetime.max.time(), tzinfo=UTC)
