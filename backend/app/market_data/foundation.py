"""Run-level quality, metric, fundamental, and coverage publication for Step 1."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CorporateAction,
    DataCoverageRun,
    DataQualityResult,
    FundamentalsSnapshot,
    MarketDataFetchResult,
    PriceDailyAdjusted,
    PriceDailyRaw,
    ScoreCalibration,
    SecurityAlias,
    StockMetricDaily,
    TradingCalendar,
)
from backend.app.market_data.metrics import (
    METHODOLOGY_VERSION,
    Calibration,
    MetricValues,
    calculate_metric_values,
    calibrate_and_score,
)
from backend.app.market_data.quality import SymbolQuality, evaluate_symbol_quality
from backend.app.market_data.service import active_nifty200_instruments
from backend.app.market_data.types import DailyPrice, MarketInstrument
from backend.app.market_data.yahoo import YahooFinanceClient

FUNDAMENTAL_STALE_DAYS = 120
QUALITY_VERSION = "nifty200-quality-v1"
SpotCheckProvider = Callable[[str, date], float | None]


def _latest_adjusted(session: Session, security_id: UUID) -> list[PriceDailyAdjusted]:
    rows = session.scalars(
        select(PriceDailyAdjusted)
        .where(PriceDailyAdjusted.security_id == security_id)
        .order_by(PriceDailyAdjusted.trade_date, PriceDailyAdjusted.computed_at.desc())
    ).all()
    latest: dict[date, PriceDailyAdjusted] = {}
    for row in rows:
        latest.setdefault(row.trade_date, row)
    return list(latest.values())


def _latest_raw(session: Session, security_id: UUID) -> list[PriceDailyRaw]:
    rows = session.scalars(
        select(PriceDailyRaw)
        .where(PriceDailyRaw.security_id == security_id, PriceDailyRaw.source == "yfinance")
        .order_by(PriceDailyRaw.trade_date, PriceDailyRaw.source_revision.desc())
    ).all()
    latest: dict[date, PriceDailyRaw] = {}
    for row in rows:
        latest.setdefault(row.trade_date, row)
    return list(latest.values())


def _series_inputs(
    session: Session, instrument: MarketInstrument
) -> tuple[list[DailyPrice], pd.Series, pd.Series, pd.Series, datetime | None]:
    adjusted = _latest_adjusted(session, instrument.security_id)
    raw = _latest_raw(session, instrument.security_id)
    adjusted_by_date = {row.trade_date: row for row in adjusted}
    raw_by_date = {row.trade_date: row for row in raw}
    common_dates = sorted(adjusted_by_date.keys() & raw_by_date.keys())
    prices = [
        DailyPrice(
            trade_date=day,
            open=raw_by_date[day].open,
            high=raw_by_date[day].high,
            low=raw_by_date[day].low,
            close=raw_by_date[day].close,
            adjusted_close=adjusted_by_date[day].adjusted_close,
            volume=raw_by_date[day].volume,
        )
        for day in common_dates
    ]
    index = pd.Index(common_dates, dtype="object")
    adjusted_series = pd.Series(
        [float(adjusted_by_date[day].adjusted_close) for day in common_dates], index=index
    )
    raw_close = pd.Series([float(raw_by_date[day].close) for day in common_dates], index=index)
    volume = pd.Series([raw_by_date[day].volume for day in common_dates], index=index)
    cutoff = max((row.computed_at for row in adjusted), default=None)
    return prices, adjusted_series, raw_close, volume, cutoff


_trading_calendar_cache: set[date] | None = None


def _get_all_trading_days(session: Session) -> set[date]:
    global _trading_calendar_cache
    if _trading_calendar_cache is None:
        _trading_calendar_cache = set(
            session.scalars(
                select(TradingCalendar.trading_date).where(
                    TradingCalendar.exchange == "NSE",
                    TradingCalendar.is_trading_day.is_(True),
                )
            ).all()
        )
    return _trading_calendar_cache


def _expected_sessions(session: Session, start: date, end: date) -> set[date] | None:
    all_days = _get_all_trading_days(session)
    days = {d for d in all_days if start <= d <= end}
    return days or None


def _quality_for_instrument(
    session: Session,
    run_id: UUID,
    instrument: MarketInstrument,
    prices: list[DailyPrice],
    as_of: date,
    failed_reason: str | None = None,
    corporate_actions: set[date] | None = None,
) -> SymbolQuality:
    if failed_reason is not None:
        return SymbolQuality(
            "fail",
            (f"fetch_failed: {failed_reason}",),
            len(prices),
            None,
            prices[-1].trade_date if prices else None,
        )
    if corporate_actions is not None:
        actions = corporate_actions
    else:
        actions = set(
            session.scalars(
                select(CorporateAction.ex_date).where(
                    CorporateAction.security_id == instrument.security_id
                )
            ).all()
        )
    start = prices[0].trade_date if prices else as_of - timedelta(days=5 * 366)
    return evaluate_symbol_quality(
        prices,
        expected_sessions=_expected_sessions(session, start, as_of),
        corporate_action_dates=actions,
        as_of=as_of,
    )


def _upsert_quality(
    session: Session,
    run_id: UUID,
    instrument: MarketInstrument,
    quality: SymbolQuality,
    checked_at: datetime,
) -> None:
    row = session.scalar(
        select(DataQualityResult).where(
            DataQualityResult.run_id == run_id,
            DataQualityResult.security_id == instrument.security_id,
        )
    )
    values = {
        "symbol": instrument.symbol,
        "status": quality.status,
        "reasons": {"codes": list(quality.reasons), "methodology_version": QUALITY_VERSION},
        "observations": quality.observations,
        "expected_sessions": quality.expected_sessions,
        "last_trade_date": quality.last_trade_date,
        "checked_at": checked_at,
    }
    if row is None:
        session.add(DataQualityResult(run_id=run_id, security_id=instrument.security_id, **values))
    else:
        for key, value in values.items():
            setattr(row, key, value)


def _decimal(value: float | None, scale: str = "0.000000000001") -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(scale))


def _upsert_metric(
    session: Session,
    *,
    run_id: UUID,
    instrument: MarketInstrument,
    metric_date: date,
    metric: MetricValues,
    quality: SymbolQuality,
    source_data_as_of: datetime | None,
    computed_at: datetime,
) -> None:
    row = session.scalar(
        select(StockMetricDaily).where(
            StockMetricDaily.security_id == instrument.security_id,
            StockMetricDaily.metric_date == metric_date,
            StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
        )
    )
    factors = metric.factor_scores
    values: dict[str, Any] = {
        "symbol": instrument.symbol,
        "volatility_1m": _decimal(metric.volatility_1m),
        "volatility_3m": _decimal(metric.volatility_3m),
        "volatility_6m": _decimal(metric.volatility_6m),
        "volatility_1y": _decimal(metric.volatility_1y),
        "downside_volatility": _decimal(metric.downside_volatility),
        "max_drawdown": _decimal(metric.max_drawdown),
        "beta_nifty50": _decimal(metric.beta_nifty50),
        "average_traded_value_20d": _decimal(metric.average_traded_value_20d, "0.000001"),
        "factor_volatility": _decimal(factors.get("volatility")),
        "factor_downside": _decimal(factors.get("downside")),
        "factor_drawdown": _decimal(factors.get("drawdown")),
        "factor_beta": _decimal(factors.get("beta")),
        "factor_instability": _decimal(factors.get("instability")),
        "score": _decimal(metric.score, "0.0001"),
        "quality_status": quality.status,
        "observations_used": metric.observations_used,
        "missing_reasons": metric.missing_reasons,
        "source_data_as_of": source_data_as_of,
        "computed_at": computed_at,
    }
    if row is None:
        session.add(
            StockMetricDaily(
                run_id=run_id,
                security_id=instrument.security_id,
                metric_date=metric_date,
                methodology_version=METHODOLOGY_VERSION,
                **values,
            )
        )
    else:
        comparable = {key: getattr(row, key) for key in values}
        if comparable != values:
            for key, value in values.items():
                setattr(row, key, value)
            row.run_id = run_id


def _upsert_calibration(
    session: Session,
    run_id: UUID,
    metric_date: date,
    calibration: Calibration,
    computed_at: datetime,
) -> None:
    row = session.scalar(
        select(ScoreCalibration).where(
            ScoreCalibration.calibration_date == metric_date,
            ScoreCalibration.factor == calibration.factor,
            ScoreCalibration.methodology_version == METHODOLOGY_VERSION,
        )
    )
    values = {
        "run_id": run_id,
        "lower_percentile": _decimal(calibration.lower_percentile, "0.000001"),
        "upper_percentile": _decimal(calibration.upper_percentile, "0.000001"),
        "lower_value": _decimal(calibration.lower_value),
        "upper_value": _decimal(calibration.upper_value),
        "eligible_count": calibration.eligible_count,
        "computed_at": computed_at,
    }
    if row is None:
        session.add(
            ScoreCalibration(
                calibration_date=metric_date,
                factor=calibration.factor,
                methodology_version=METHODOLOGY_VERSION,
                **values,
            )
        )
    else:
        for key, value in values.items():
            setattr(row, key, value)


def calculate_and_persist_daily_metrics(
    session: Session, *, run_id: UUID, as_of: date
) -> tuple[dict[str, SymbolQuality], list[MetricValues]]:
    """Atomically calculate quality and metrics for all 200 current constituents."""
    instruments = active_nifty200_instruments(session, as_of)
    if len(instruments) != 200:
        raise ValueError(f"Expected 200 NIFTY 200 instruments, received {len(instruments)}")
    benchmark_alias = session.scalar(
        select(SecurityAlias).where(
            SecurityAlias.symbol == "^NSEI", SecurityAlias.valid_to.is_(None)
        )
    )
    benchmark = pd.Series(dtype=float)
    if benchmark_alias is not None:
        _, benchmark, _, _, _ = _series_inputs(
            session, MarketInstrument(benchmark_alias.security_id, "^NSEI", "^NSEI")
        )

    checked_at = datetime.now(UTC)
    failed_fetches = {
        res.security_id: res.reason or "provider_failure"
        for res in session.scalars(
            select(MarketDataFetchResult).where(
                MarketDataFetchResult.run_id == run_id,
                MarketDataFetchResult.status == "failed",
            )
        ).all()
    }
    corp_actions: dict[UUID, set[date]] = {}
    for sec_id, ex_date in session.execute(
        select(CorporateAction.security_id, CorporateAction.ex_date)
    ).all():
        corp_actions.setdefault(sec_id, set()).add(ex_date)

    qualities: dict[str, SymbolQuality] = {}
    metrics: list[MetricValues] = []
    inputs: dict[str, tuple[MarketInstrument, datetime | None]] = {}
    for instrument in instruments:
        prices, adjusted, raw_close, volume, cutoff = _series_inputs(session, instrument)
        quality = _quality_for_instrument(
            session,
            run_id,
            instrument,
            prices,
            as_of,
            failed_reason=failed_fetches.get(instrument.security_id),
            corporate_actions=corp_actions.get(instrument.security_id, set()),
        )
        qualities[instrument.symbol] = quality
        _upsert_quality(session, run_id, instrument, quality, checked_at)
        metric = calculate_metric_values(instrument.symbol, adjusted, benchmark, raw_close, volume)
        if quality.status == "fail":
            metric = MetricValues(
                symbol=instrument.symbol,
                metric_date=metric.metric_date,
                observations_used=metric.observations_used,
                missing_reasons={"all_metrics": "excluded_by_quality_gate"},
            )
        metrics.append(metric)
        inputs[instrument.symbol] = (instrument, cutoff)

    calibrations = calibrate_and_score(
        [metric for metric in metrics if qualities[metric.symbol].status != "fail"]
    )
    metric_date = max(
        (metric.metric_date for metric in metrics if metric.metric_date is not None),
        default=as_of,
    )
    for calibration in calibrations.values():
        _upsert_calibration(session, run_id, metric_date, calibration, checked_at)
    for metric in metrics:
        instrument, cutoff = inputs[metric.symbol]
        _upsert_metric(
            session,
            run_id=run_id,
            instrument=instrument,
            metric_date=metric_date,
            metric=metric,
            quality=qualities[metric.symbol],
            source_data_as_of=cutoff,
            computed_at=checked_at,
        )
    session.flush()
    return qualities, metrics


def fetch_and_persist_fundamentals(
    session: Session,
    *,
    as_of: date,
    client: YahooFinanceClient | None = None,
) -> dict[str, str]:
    """Persist only observed fields; return per-symbol failures for coverage reasons."""
    provider = client or YahooFinanceClient()
    failures: dict[str, str] = {}
    for instrument in active_nifty200_instruments(session, as_of):
        try:
            reporting_date, fields, fetched_at = provider.fundamentals(instrument.yahoo_symbol)
            for field_name, value in fields.items():
                existing = session.scalar(
                    select(FundamentalsSnapshot).where(
                        FundamentalsSnapshot.security_id == instrument.security_id,
                        FundamentalsSnapshot.field == field_name,
                        FundamentalsSnapshot.as_of == reporting_date,
                        FundamentalsSnapshot.source == "yfinance",
                    )
                )
                wrapped = {"value": value}
                if existing is None:
                    session.add(
                        FundamentalsSnapshot(
                            security_id=instrument.security_id,
                            symbol=instrument.symbol,
                            field=field_name,
                            value=wrapped,
                            as_of=reporting_date,
                            fetched_at=fetched_at,
                            source="yfinance",
                        )
                    )
                elif existing.value != wrapped:
                    existing.value = wrapped
                    existing.fetched_at = fetched_at
        except Exception as exc:
            failures[instrument.symbol] = f"{type(exc).__name__}: {exc}"
    session.flush()
    return failures


def reproducible_spot_checks(
    symbols: list[str],
    *,
    as_of: date,
    second_source: SpotCheckProvider | None,
    primary_values: dict[str, float],
) -> dict[str, object]:
    seed = int(hashlib.sha256(f"{as_of}:{METHODOLOGY_VERSION}".encode()).hexdigest()[:16], 16)
    selected = sorted(random.Random(seed).sample(sorted(symbols), min(10, len(symbols))))
    if second_source is None:
        return {
            "status": "unavailable",
            "reason": "independent_second_source_not_configured",
            "selected_symbols": selected,
            "results": [],
        }
    results: list[dict[str, object]] = []
    for symbol in selected:
        secondary = second_source(symbol, as_of)
        primary = primary_values.get(symbol)
        if primary is None or secondary is None:
            results.append({"symbol": symbol, "status": "unavailable"})
        else:
            results.append(
                {
                    "symbol": symbol,
                    "status": "compared",
                    "primary": primary,
                    "secondary": secondary,
                    "absolute_difference": abs(primary - secondary),
                    "relative_difference": abs(primary - secondary) / abs(secondary)
                    if secondary != 0
                    else None,
                }
            )
    return {"status": "completed", "selected_symbols": selected, "results": results}


def persist_coverage_report(
    session: Session,
    *,
    run_id: UUID,
    as_of: date,
    spot_checks: dict[str, object],
    fundamental_failures: dict[str, str] | None = None,
) -> DataCoverageRun:
    instruments = active_nifty200_instruments(session, as_of)
    ids = [item.security_id for item in instruments]
    symbols = {item.security_id: item.symbol for item in instruments}
    verified_ids = set(
        session.scalars(
            select(SecurityAlias.security_id).where(
                SecurityAlias.security_id.in_(ids),
                SecurityAlias.verification_status == "verified",
                SecurityAlias.valid_to.is_(None),
            )
        ).all()
    )
    quality_rows = session.scalars(
        select(DataQualityResult).where(
            DataQualityResult.run_id == run_id,
            DataQualityResult.security_id.in_(ids),
        )
    ).all()
    quality_by_id = {row.security_id: row for row in quality_rows}
    metric_date = session.scalar(
        select(func.max(StockMetricDaily.metric_date)).where(
            StockMetricDaily.security_id.in_(ids),
            StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
        )
    )
    metric_rows = session.scalars(
        select(StockMetricDaily).where(
            StockMetricDaily.security_id.in_(ids),
            StockMetricDaily.metric_date == metric_date,
            StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
        )
    ).all()
    metrics_ready = {row.security_id for row in metric_rows if row.score is not None}
    fresh_cutoff = as_of - timedelta(days=FUNDAMENTAL_STALE_DAYS)
    fundamental_ids = set(
        session.scalars(
            select(FundamentalsSnapshot.security_id)
            .where(
                FundamentalsSnapshot.security_id.in_(ids),
                FundamentalsSnapshot.as_of >= fresh_cutoff,
            )
            .distinct()
        ).all()
    )
    enough_history = {
        security_id for security_id, row in quality_by_id.items() if row.observations >= 252
    }
    quality_pass = {
        security_id for security_id, row in quality_by_id.items() if row.status == "pass"
    }
    exclusions: list[dict[str, object]] = []
    for security_id in ids:
        reasons: list[str] = []
        if security_id not in verified_ids:
            reasons.append("ticker_not_verified")
        quality = quality_by_id.get(security_id)
        if quality is None:
            reasons.append("quality_not_evaluated")
        elif quality.status == "fail":
            codes = quality.reasons.get("codes", [])
            if isinstance(codes, list):
                reasons.extend(str(code) for code in codes)
        if security_id not in enough_history:
            reasons.append("insufficient_history")
        if security_id not in metrics_ready:
            reasons.append("metrics_unavailable")
        if security_id not in fundamental_ids:
            failure = (fundamental_failures or {}).get(symbols[security_id])
            reasons.append(
                f"fundamentals_unavailable: {failure}"
                if failure
                else "fundamentals_stale_or_missing"
            )
        if reasons:
            exclusions.append({"symbol": symbols[security_id], "reasons": sorted(set(reasons))})

    now = datetime.now(UTC)
    existing = session.scalar(select(DataCoverageRun).where(DataCoverageRun.run_id == run_id))
    values = {
        "universe_count": len(ids),
        "verified_ticker_count": len(verified_ids),
        "enough_history_count": len(enough_history),
        "quality_pass_count": len(quality_pass),
        "metrics_ready_count": len(metrics_ready),
        "fundamentals_ready_count": len(fundamental_ids),
        "excluded_symbols": {"items": exclusions},
        "spot_checks": spot_checks,
        "data_date": metric_date,
        "last_update_time": now,
        "status": "completed" if not exclusions else "partial",
    }
    if existing is None:
        existing = DataCoverageRun(run_id=run_id, **values)
        session.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    session.flush()
    return existing


def coverage_payload(row: DataCoverageRun) -> dict[str, object]:
    return {
        "run_id": str(row.run_id),
        "status": row.status,
        "universe_count": row.universe_count,
        "verified_ticker_count": row.verified_ticker_count,
        "enough_history_count": row.enough_history_count,
        "quality_pass_count": row.quality_pass_count,
        "metrics_ready_count": row.metrics_ready_count,
        "fundamentals_ready_count": row.fundamentals_ready_count,
        "data_date": row.data_date,
        "last_update_time": row.last_update_time,
        "excluded_symbols": row.excluded_symbols.get("items", []),
        "spot_checks": row.spot_checks,
    }
