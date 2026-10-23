"""Incremental persistence service for NIFTY 200 daily market data."""

import hashlib
import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.app.db.models import (
    CorporateAction,
    MarketDataFetchResult,
    PipelineRun,
    PriceDailyAdjusted,
    PriceDailyRaw,
    Security,
    SecurityAlias,
    Universe,
    UniverseMembership,
)
from backend.app.market_data.quality import validate_prices
from backend.app.market_data.types import DailyPrice, IngestionSummary, MarketInstrument
from backend.app.market_data.yahoo import PROVIDER_VERSION, YahooFinanceClient, exclusive_end

SOURCE = "yfinance"
WORKFLOW = "daily_market_data"
CODE_VERSION = "market-data-v2"
ADJUSTMENT_METHOD = "yfinance-adjclose-v1"
INCREMENTAL_OVERLAP_SESSIONS = 10
BENCHMARK_SYMBOL = "^NSEI"


@dataclass(frozen=True, slots=True)
class PersistCounts:
    raw_revisions_inserted: int = 0
    adjusted_inserted: int = 0
    adjusted_updated: int = 0
    corporate_actions_inserted: int = 0
    corporate_actions_updated: int = 0


def active_nifty200_instruments(session: Session, as_of: date) -> list[MarketInstrument]:
    rows = session.execute(
        select(
            UniverseMembership.security_id,
            SecurityAlias.symbol,
            SecurityAlias.provider_symbol,
        )
        .join(Universe, Universe.id == UniverseMembership.universe_id)
        .join(SecurityAlias, SecurityAlias.security_id == UniverseMembership.security_id)
        .where(
            Universe.name == "NIFTY 200",
            UniverseMembership.valid_from <= as_of,
            (UniverseMembership.valid_to.is_(None) | (UniverseMembership.valid_to >= as_of)),
            SecurityAlias.exchange == "NSE",
            SecurityAlias.valid_from <= as_of,
            (SecurityAlias.valid_to.is_(None) | (SecurityAlias.valid_to >= as_of)),
        )
        .order_by(SecurityAlias.symbol)
    ).all()
    return [
        MarketInstrument(
            security_id=row.security_id,
            symbol=row.symbol,
            provider_symbol=row.provider_symbol,
        )
        for row in rows
    ]


def ensure_nifty50_benchmark(session: Session, as_of: date) -> MarketInstrument:
    """Persist the non-equity benchmark without fabricating an ISIN."""
    alias = session.scalar(
        select(SecurityAlias).where(
            SecurityAlias.symbol == BENCHMARK_SYMBOL,
            SecurityAlias.exchange == "INDEX",
            SecurityAlias.valid_to.is_(None),
        )
    )
    if alias is None:
        security = Security(
            isin=None,
            company_name="NIFTY 50 Index",
            sector=None,
            industry="Broad Market Index",
            currency="INR",
            is_active=True,
        )
        session.add(security)
        session.flush()
        alias = SecurityAlias(
            security_id=security.id,
            symbol=BENCHMARK_SYMBOL,
            exchange="INDEX",
            valid_from=as_of,
            source="yfinance",
            ingested_at=datetime.now(UTC),
            provider_symbol=BENCHMARK_SYMBOL,
        )
        session.add(alias)
        session.flush()
    return MarketInstrument(alias.security_id, BENCHMARK_SYMBOL, BENCHMARK_SYMBOL)


def incremental_start(session: Session, security_id: UUID, requested_start: date) -> date:
    recent_dates = session.scalars(
        select(PriceDailyRaw.trade_date)
        .where(
            PriceDailyRaw.security_id == security_id,
            PriceDailyRaw.source == SOURCE,
        )
        .distinct()
        .order_by(PriceDailyRaw.trade_date.desc())
        .limit(INCREMENTAL_OVERLAP_SESSIONS)
    ).all()
    if not recent_dates:
        return requested_start
    return max(requested_start, min(recent_dates))


def adjusted_history_changed(
    session: Session,
    security_id: UUID,
    prices: list[DailyPrice],
    *,
    provisional_date: date | None = None,
) -> bool:
    """Compare the re-fetched overlap with the latest stored adjusted revision."""
    if not prices:
        return False
    dates = [item.trade_date for item in prices]
    rows = session.scalars(
        select(PriceDailyAdjusted)
        .where(
            PriceDailyAdjusted.security_id == security_id,
            PriceDailyAdjusted.trade_date.in_(dates),
            PriceDailyAdjusted.method_version.like(f"{ADJUSTMENT_METHOD}-r%"),
        )
        .order_by(PriceDailyAdjusted.trade_date, PriceDailyAdjusted.computed_at.desc())
    ).all()
    latest: dict[date, Decimal] = {}
    for row in rows:
        latest.setdefault(row.trade_date, row.adjusted_close)
    return any(
        item.trade_date in latest
        and item.trade_date != provisional_date
        and _six_places(item.adjusted_close) != _six_places(latest[item.trade_date])
        for item in prices
    )


def _six_places(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))


def _ten_places(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0000000001"))


def _raw_values(price: DailyPrice) -> tuple[Decimal, Decimal, Decimal, Decimal, int]:
    return (
        _six_places(price.open),
        _six_places(price.high),
        _six_places(price.low),
        _six_places(price.close),
        price.volume,
    )


def persist_prices(
    session: Session,
    instrument: MarketInstrument,
    prices: tuple[DailyPrice, ...],
    ingested_at: datetime,
    *,
    run_id: UUID | None = None,
    provider_version: str = PROVIDER_VERSION,
) -> PersistCounts:
    if not prices:
        return PersistCounts()

    dates = [price.trade_date for price in prices]
    raw_rows = session.scalars(
        select(PriceDailyRaw)
        .where(
            PriceDailyRaw.security_id == instrument.security_id,
            PriceDailyRaw.source == SOURCE,
            PriceDailyRaw.trade_date.in_(dates),
        )
        .order_by(PriceDailyRaw.trade_date, PriceDailyRaw.source_revision.desc())
    ).all()
    latest_raw: dict[date, PriceDailyRaw] = {}
    for raw_row in raw_rows:
        latest_raw.setdefault(raw_row.trade_date, raw_row)

    adjusted_rows = session.scalars(
        select(PriceDailyAdjusted).where(
            PriceDailyAdjusted.security_id == instrument.security_id,
            PriceDailyAdjusted.method_version.like(f"{ADJUSTMENT_METHOD}-r%"),
            PriceDailyAdjusted.trade_date.in_(dates),
        )
    ).all()
    adjusted_by_date: dict[date, list[PriceDailyAdjusted]] = {}
    for adjusted_row in adjusted_rows:
        adjusted_by_date.setdefault(adjusted_row.trade_date, []).append(adjusted_row)

    action_rows = session.scalars(
        select(CorporateAction).where(
            CorporateAction.security_id == instrument.security_id,
            CorporateAction.source == SOURCE,
            CorporateAction.ex_date.in_(dates),
        )
    ).all()
    action_by_key = {
        (action_row.action_type, action_row.ex_date): action_row for action_row in action_rows
    }

    raw_inserted = adjusted_inserted = adjusted_updated = 0
    actions_inserted = actions_updated = 0
    for price in prices:
        raw_values = _raw_values(price)
        prior_raw = latest_raw.get(price.trade_date)
        prior_values = None
        if prior_raw is not None:
            prior_values = (
                prior_raw.open,
                prior_raw.high,
                prior_raw.low,
                prior_raw.close,
                prior_raw.volume,
            )
        if prior_values != raw_values:
            revision = 1 if prior_raw is None else prior_raw.source_revision + 1
            session.add(
                PriceDailyRaw(
                    security_id=instrument.security_id,
                    trade_date=price.trade_date,
                    open=raw_values[0],
                    high=raw_values[1],
                    low=raw_values[2],
                    close=raw_values[3],
                    volume=price.volume,
                    currency="INR",
                    source=SOURCE,
                    source_revision=revision,
                    ingested_at=ingested_at,
                    provider_version=provider_version,
                    pipeline_run_id=run_id,
                    quality_flags={"flags": list(price.quality_flags)},
                )
            )
            raw_inserted += 1

        factor = _ten_places(price.adjusted_close / price.close)
        adjusted_values = (
            _six_places(price.open * factor),
            _six_places(price.high * factor),
            _six_places(price.low * factor),
            _six_places(price.adjusted_close),
            factor,
        )
        prior_adjustments = adjusted_by_date.get(price.trade_date, [])
        latest_adjustment = max(
            prior_adjustments,
            key=lambda row: int(row.method_version.rsplit("-r", 1)[-1]),
            default=None,
        )
        existing = None
        if latest_adjustment is not None:
            existing = (
                latest_adjustment.adjusted_open,
                latest_adjustment.adjusted_high,
                latest_adjustment.adjusted_low,
                latest_adjustment.adjusted_close,
                latest_adjustment.adjustment_factor,
            )
        if existing != adjusted_values:
            adjustment_revision = 1
            if latest_adjustment is not None:
                adjustment_revision = int(latest_adjustment.method_version.rsplit("-r", 1)[-1]) + 1
            session.add(
                PriceDailyAdjusted(
                    security_id=instrument.security_id,
                    trade_date=price.trade_date,
                    adjusted_open=adjusted_values[0],
                    adjusted_high=adjusted_values[1],
                    adjusted_low=adjusted_values[2],
                    adjusted_close=adjusted_values[3],
                    adjustment_factor=adjusted_values[4],
                    method_version=f"{ADJUSTMENT_METHOD}-r{adjustment_revision}",
                    computed_at=ingested_at,
                )
            )
            adjusted_inserted += 1

        for action_type, value in (
            ("dividend", price.dividend),
            ("stock_split", price.stock_split),
        ):
            if value == 0:
                continue
            key = (action_type, price.trade_date)
            action = action_by_key.get(key)
            normalized_value = value.quantize(Decimal("0.00000001"))
            details: dict[str, object] = {"yahoo_symbol": instrument.yahoo_symbol}
            if action is None:
                session.add(
                    CorporateAction(
                        security_id=instrument.security_id,
                        action_type=action_type,
                        ex_date=price.trade_date,
                        value=normalized_value,
                        details=details,
                        source=SOURCE,
                        ingested_at=ingested_at,
                    )
                )
                actions_inserted += 1
            elif action.value != normalized_value or action.details != details:
                action.value = normalized_value
                action.details = details
                action.ingested_at = ingested_at
                actions_updated += 1

    return PersistCounts(
        raw_revisions_inserted=raw_inserted,
        adjusted_inserted=adjusted_inserted,
        adjusted_updated=adjusted_updated,
        corporate_actions_inserted=actions_inserted,
        corporate_actions_updated=actions_updated,
    )


def _configuration_hash(start: date, end: date, symbols: set[str] | None) -> str:
    payload = json.dumps(
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "source": SOURCE,
            "symbols": sorted(symbols) if symbols else None,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _persist_with_retry(
    session: Session,
    instrument: MarketInstrument,
    prices: tuple[DailyPrice, ...],
    *,
    run_id: UUID | None = None,
    provider_version: str = PROVIDER_VERSION,
) -> PersistCounts:
    retrying = Retrying(
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=1, max=16),
        retry=retry_if_exception_type(OperationalError),
        reraise=True,
    )
    for attempt in retrying:
        with attempt:
            try:
                counts = persist_prices(
                    session,
                    instrument,
                    prices,
                    datetime.now(UTC),
                    run_id=run_id,
                    provider_version=provider_version,
                )
                session.commit()
                return counts
            except OperationalError:
                session.rollback()
                raise
    raise RuntimeError("Unreachable persistence retry state")


def ingest_nifty200_prices(
    session: Session,
    start: date,
    end: date,
    snapshot_root: Path,
    client: YahooFinanceClient | None = None,
    max_workers: int = 8,
    symbols: set[str] | None = None,
    provisional_date: date | None = None,
) -> IngestionSummary:
    """Download and persist prices through *end*, committing each symbol independently."""
    if start > end:
        raise ValueError("Start date must be on or before end date")
    if not 1 <= max_workers <= 16:
        raise ValueError("max_workers must be between 1 and 16")

    provider = client or YahooFinanceClient()
    instruments = active_nifty200_instruments(session, end)
    if not symbols:
        instruments.append(ensure_nifty50_benchmark(session, end))
        session.commit()
    if symbols:
        requested = {symbol.upper() for symbol in symbols}
        instruments = [instrument for instrument in instruments if instrument.symbol in requested]
        missing = requested.difference(instrument.symbol for instrument in instruments)
        if missing:
            raise ValueError(f"Symbols are not active NIFTY 200 members: {sorted(missing)}")
    if not instruments:
        raise ValueError("No active NIFTY 200 instruments were found")

    now = datetime.now(UTC)
    run = PipelineRun(
        workflow=WORKFLOW,
        code_version=CODE_VERSION,
        configuration_hash=_configuration_hash(start, end, symbols),
        status="running",
        started_at=now,
    )
    session.add(run)
    session.commit()
    run_id = run.id
    run_directory = snapshot_root / str(run_id)
    run_directory.mkdir(parents=True, exist_ok=False)
    provider_version = getattr(provider, "library_version", PROVIDER_VERSION)
    summary = IngestionSummary(requested_symbols=len(instruments), run_id=run_id)

    requests = [
        (instrument, incremental_start(session, instrument.security_id, start))
        for instrument in instruments
    ]
    futures: dict[Future[tuple[Any, list[DailyPrice]]], MarketInstrument] = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="yahoo") as executor:
        for instrument, symbol_start in requests:
            future = executor.submit(
                provider.history,
                instrument.yahoo_symbol,
                symbol_start,
                exclusive_end(end),
            )
            futures[future] = instrument

        for future in as_completed(futures):
            instrument = futures[future]
            try:
                frame, downloaded = future.result()
                frame.to_csv(run_directory / f"{instrument.yahoo_symbol}.csv")
                full_refetch = adjusted_history_changed(
                    session,
                    instrument.security_id,
                    downloaded,
                    provisional_date=provisional_date,
                )
                requested_from = incremental_start(session, instrument.security_id, start)
                if full_refetch and requested_from > start:
                    frame, downloaded = provider.history(
                        instrument.yahoo_symbol, start, exclusive_end(end)
                    )
                    frame.to_csv(run_directory / f"{instrument.yahoo_symbol}.csv")
                    summary.full_refetches += 1
                if not downloaded:
                    raise ValueError("provider_returned_no_daily_prices")
                if provisional_date and not any(
                    price.trade_date == provisional_date for price in downloaded
                ):
                    raise ValueError("provider_has_no_current_session_prices")
                quality = validate_prices(downloaded)
                counts = _persist_with_retry(
                    session,
                    instrument,
                    quality.accepted,
                    run_id=run_id,
                    provider_version=provider_version,
                )

                session.add(
                    MarketDataFetchResult(
                        run_id=run_id,
                        security_id=instrument.security_id,
                        symbol=instrument.symbol,
                        provider_symbol=instrument.yahoo_symbol,
                        status="completed",
                        requested_start=requested_from,
                        requested_end=end,
                        rows_received=len(downloaded),
                        full_refetch=full_refetch,
                        provider=SOURCE,
                        provider_version=provider_version,
                        fetched_at=datetime.now(UTC),
                    )
                )
                session.commit()

                summary.completed_symbols += 1
                summary.downloaded_rows += len(downloaded)
                summary.rejected_rows += quality.rejected_rows
                summary.warnings += quality.warning_count
                summary.raw_revisions_inserted += counts.raw_revisions_inserted
                summary.adjusted_inserted += counts.adjusted_inserted
                summary.adjusted_updated += counts.adjusted_updated
                summary.corporate_actions_inserted += counts.corporate_actions_inserted
                summary.corporate_actions_updated += counts.corporate_actions_updated
            except Exception as exc:  # one provider/security failure must not discard other symbols
                session.rollback()
                reason = f"{type(exc).__name__}: {exc}"
                summary.failed_symbols[instrument.symbol] = reason
                session.add(
                    MarketDataFetchResult(
                        run_id=run_id,
                        security_id=instrument.security_id,
                        symbol=instrument.symbol,
                        provider_symbol=instrument.yahoo_symbol,
                        status="failed",
                        reason=reason,
                        requested_start=incremental_start(session, instrument.security_id, start),
                        requested_end=end,
                        rows_received=0,
                        provider=SOURCE,
                        provider_version=provider_version,
                        fetched_at=datetime.now(UTC),
                    )
                )
                session.commit()

    finished_run = session.get(PipelineRun, run_id)
    if finished_run is None:
        raise RuntimeError(f"Pipeline run {run_id} disappeared")
    finished_run.completed_at = datetime.now(UTC)
    finished_run.status = "completed" if not summary.failed_symbols else "partial"
    finished_run.row_counts = summary.as_dict()
    finished_run.quality_summary = {
        "rejected_rows": summary.rejected_rows,
        "warnings": summary.warnings,
    }
    if summary.failed_symbols:
        finished_run.error_summary = json.dumps(summary.failed_symbols, sort_keys=True)
    session.commit()
    return summary
