"""Service layer for macroeconomic series, market regime, and sector sensitivities (D3, D4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    MacroObservation,
    MacroSeriesDefinition,
    MarketRegime,
    SectorMacroSensitivity,
    Security,
    SecurityAlias,
)
from backend.app.macro.regime import classify_market_regime
from backend.app.macro.schemas import (
    MacroObservationOut,
    MacroSeriesDefinitionOut,
    MacroSeriesDetailOut,
    MarketRegimeOut,
    SectorMacroSensitivityOut,
    StockMacroExposureOut,
)


def get_latest_market_regime(
    session: Session,
    as_of: date | None = None,
    cutoff: datetime | None = None,
) -> MarketRegimeOut:
    """Retrieve the latest point-in-time market regime, generating on-the-fly if needed."""
    query = select(MarketRegime)
    if as_of:
        query = query.where(MarketRegime.as_of <= as_of)
    query = query.order_by(desc(MarketRegime.as_of)).limit(1)

    regime_row = session.scalars(query).first()

    if not regime_row:
        # If no regime computed yet, calculate for as_of or today
        target_date = as_of or datetime.now(UTC).date()
        calc_result = classify_market_regime(session, as_of=target_date, cutoff=cutoff)
        return MarketRegimeOut(
            as_of=calc_result.as_of,
            regime=calc_result.regime,
            features=calc_result.features,
            config_version=calc_result.config_version,
            computed_at=datetime.now(UTC),
        )

    return MarketRegimeOut(
        as_of=regime_row.as_of,
        regime=regime_row.regime,
        features=regime_row.features,
        config_version=regime_row.config_version,
        computed_at=regime_row.created_at,
    )


def list_macro_series(session: Session) -> list[MacroSeriesDefinitionOut]:
    """List all registered macro series definitions."""
    rows = session.scalars(
        select(MacroSeriesDefinition)
        .where(MacroSeriesDefinition.is_active == True)  # noqa: E712
        .order_by(MacroSeriesDefinition.series_key.asc())
    ).all()

    return [
        MacroSeriesDefinitionOut(
            series_key=r.series_key,
            name=r.name,
            source=r.source,
            frequency=r.frequency,
            unit=r.unit,
            license_note=r.license_note,
            is_active=r.is_active,
        )
        for r in rows
    ]


def get_macro_series_detail(
    session: Session,
    series_key: str,
    as_of: date | None = None,
    limit: int = 500,
) -> MacroSeriesDetailOut | None:
    """Retrieve series definition and observations point-in-time."""
    series_def = session.scalars(
        select(MacroSeriesDefinition).where(MacroSeriesDefinition.series_key == series_key)
    ).first()

    if not series_def:
        return None

    obs_query = select(MacroObservation).where(MacroObservation.series_key == series_key)
    if as_of:
        obs_query = obs_query.where(MacroObservation.obs_date <= as_of)

    obs_query = obs_query.order_by(desc(MacroObservation.obs_date)).limit(limit)
    rows = session.scalars(obs_query).all()

    observations = [
        MacroObservationOut(
            obs_date=r.obs_date,
            value=r.value,
            published_at=r.published_at,
            version=r.version,
        )
        for r in reversed(rows)
    ]

    latest = observations[-1] if observations else None

    return MacroSeriesDetailOut(
        series=MacroSeriesDefinitionOut(
            series_key=series_def.series_key,
            name=series_def.name,
            source=series_def.source,
            frequency=series_def.frequency,
            unit=series_def.unit,
            license_note=series_def.license_note,
            is_active=series_def.is_active,
        ),
        observations=observations,
        total_observations=len(observations),
        latest_observation=latest,
    )


def get_industry_macro_sensitivities(
    session: Session,
    industry: str,
    as_of: date | None = None,
) -> list[SectorMacroSensitivityOut]:
    """Retrieve macro sensitivities for a specific industry."""
    # Series definitions for names
    series_map = {
        s.series_key: s.name for s in session.scalars(select(MacroSeriesDefinition)).all()
    }

    query = select(SectorMacroSensitivity).where(SectorMacroSensitivity.industry == industry)
    if as_of:
        query = query.where(SectorMacroSensitivity.window_end <= as_of)

    query = query.order_by(
        desc(SectorMacroSensitivity.window_end),
        SectorMacroSensitivity.series_key.asc(),
    )
    rows = session.scalars(query).all()

    # Deduplicate by series_key to keep latest window_end
    latest_by_series: dict[str, SectorMacroSensitivity] = {}
    for r in rows:
        if r.series_key not in latest_by_series:
            latest_by_series[r.series_key] = r

    return [
        SectorMacroSensitivityOut(
            industry=r.industry,
            series_key=r.series_key,
            series_name=series_map.get(r.series_key, r.series_key),
            window_end=r.window_end,
            beta=r.beta,
            t_stat=r.t_stat,
            n_obs=r.n_obs,
            p_value=r.p_value,
            is_significant=r.is_significant,
            config_version=r.config_version,
        )
        for r in latest_by_series.values()
    ]


def get_all_sector_sensitivities(
    session: Session,
    industry: str | None = None,
    series_key: str | None = None,
    as_of: date | None = None,
) -> list[SectorMacroSensitivityOut]:
    """Retrieve all latest sector macro sensitivities across all industries and series."""
    series_map = {
        s.series_key: s.name for s in session.scalars(select(MacroSeriesDefinition)).all()
    }

    query = select(SectorMacroSensitivity)
    if industry:
        query = query.where(SectorMacroSensitivity.industry == industry)
    if series_key:
        query = query.where(SectorMacroSensitivity.series_key == series_key)
    if as_of:
        query = query.where(SectorMacroSensitivity.window_end <= as_of)

    query = query.order_by(
        desc(SectorMacroSensitivity.window_end),
        SectorMacroSensitivity.industry.asc(),
        SectorMacroSensitivity.series_key.asc(),
    )
    rows = session.scalars(query).all()

    latest_by_pair: dict[tuple[str, str], SectorMacroSensitivity] = {}
    for r in rows:
        pair_key = (r.industry, r.series_key)
        if pair_key not in latest_by_pair:
            latest_by_pair[pair_key] = r

    return [
        SectorMacroSensitivityOut(
            industry=r.industry,
            series_key=r.series_key,
            series_name=series_map.get(r.series_key, r.series_key),
            window_end=r.window_end,
            beta=r.beta,
            t_stat=r.t_stat,
            n_obs=r.n_obs,
            p_value=r.p_value,
            is_significant=r.is_significant,
            config_version=r.config_version,
        )
        for r in latest_by_pair.values()
    ]


def get_stock_macro_profile(
    session: Session,
    symbol: str,
    as_of: date | None = None,
) -> StockMacroExposureOut | None:
    """Retrieve full macro exposure profile for a specific stock."""
    # Find security and industry
    sec_row = session.execute(
        select(Security.id, Security.industry)
        .join(SecurityAlias, SecurityAlias.security_id == Security.id)
        .where(SecurityAlias.symbol == symbol)
    ).first()

    if not sec_row:
        return None

    industry = sec_row[1] or "General"

    # Latest regime
    regime = get_latest_market_regime(session, as_of=as_of)
    multiplier = float(regime.features.get("regime_multiplier", 1.0))

    # Industry sensitivities
    sensitivities = get_industry_macro_sensitivities(session, industry, as_of=as_of)

    # Recent shocks summary from regime features or series
    recent_shocks: dict[str, Any] = {
        "vix": regime.features.get("india_vix"),
        "vol_percentile": regime.features.get("vol_percentile"),
        "corr_percentile": regime.features.get("corr_percentile"),
        "regime": regime.regime,
        "multiplier": multiplier,
    }

    limitations = [
        "Macro sensitivities are estimated via 63-day rolling OLS regressions at sector level.",
        "Insignificant sensitivities (|t| < 1.96) are marked and zeroed out (no forced exposure).",
        "Market regime classification is rule-based and descriptive (not an investment forecast).",
    ]

    return StockMacroExposureOut(
        symbol=symbol,
        industry=industry,
        regime=regime.regime,
        regime_multiplier=multiplier,
        macro_score=None,
        sensitivities=sensitivities,
        recent_shocks=recent_shocks,
        limitations=limitations,
    )
