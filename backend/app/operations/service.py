"""Freshness, alerts, watchlists, and incremental score operations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Alert,
    BenchmarkSeries,
    DataFreshness,
    EventItem,
    MacroObservation,
    MarketRegime,
    ModelConfig,
    MstCluster,
    MstRun,
    NewsItem,
    PipelineRun,
    PortfolioHolding,
    PriceDailyRaw,
    ScoreRun,
    Security,
    SecurityAlias,
    StockRiskResult,
    TextScore,
    Watchlist,
    WatchlistItem,
)
from backend.app.operations.schemas import WatchlistCreate, WatchlistItemOut, WatchlistOut
from backend.app.risk_score.service import CalculationSummary, run_stock_score_calculation


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def load_operations_config(session: Session) -> tuple[dict[str, Any], str, str]:
    row = session.scalars(
        select(ModelConfig)
        .where(
            ModelConfig.config_key == "operations_parameters",
            ModelConfig.status == "approved",
        )
        .order_by(desc(ModelConfig.created_at))
    ).first()
    if row is None:
        raise ValueError("approved operations configuration is not installed")
    return dict(row.configuration), row.version, row.configuration_hash


def freshness_status(
    now: datetime,
    last_success_at: datetime | None,
    expected_cadence_minutes: int,
    grace_minutes: int,
) -> str:
    """Classify source freshness without claiming real-time availability."""
    if expected_cadence_minutes <= 0 or grace_minutes < 0:
        raise ValueError("freshness cadence must be positive and grace non-negative")
    if last_success_at is None:
        return "unknown"
    if last_success_at.tzinfo is None or last_success_at.utcoffset() is None:
        raise ValueError("last_success_at must be timezone-aware")
    if last_success_at > now:
        raise ValueError("last_success_at cannot be after evaluation time")
    deadline = last_success_at + timedelta(minutes=expected_cadence_minutes + grace_minutes)
    return "stale" if now > deadline else "fresh"


def evaluate_freshness(session: Session, now: datetime | None = None) -> list[DataFreshness]:
    """Evaluate configured sources from actual persisted timestamps."""
    current = now or datetime.now(UTC)
    config, _, _ = load_operations_config(session)
    sources = config.get("freshness_sources", {})
    if not isinstance(sources, dict):
        raise ValueError("freshness_sources must be an object")
    observations: dict[str, tuple[datetime | None, object | None]] = {
        "prices": session.execute(
            select(func.max(PriceDailyRaw.ingested_at), func.max(PriceDailyRaw.trade_date))
        ).one(),
        "benchmark": session.execute(
            select(func.max(BenchmarkSeries.ingested_at), func.max(BenchmarkSeries.trade_date))
        ).one(),
        "filings": session.execute(
            select(func.max(EventItem.created_at), func.max(EventItem.effective_trading_date))
        ).one(),
        "news": session.execute(
            select(func.max(NewsItem.ingested_at), func.max(func.date(NewsItem.published_at)))
        ).one(),
        "macro": session.execute(
            select(func.max(MacroObservation.ingested_at), func.max(MacroObservation.obs_date))
        ).one(),
    }
    output: list[DataFreshness] = []
    for source_key, raw_policy in sorted(sources.items()):
        if not isinstance(raw_policy, dict):
            continue
        cadence = int(raw_policy["expected_cadence_minutes"])
        grace = int(raw_policy["grace_minutes"])
        success_at, data_date = observations.get(source_key, (None, None))
        row = session.get(DataFreshness, source_key) or DataFreshness(source_key=source_key)
        row.last_success_at = success_at
        row.last_data_date = cast(date | None, data_date)
        row.expected_cadence = cadence
        row.grace = grace
        row.status = freshness_status(current, success_at, cadence, grace)
        session.add(row)
        output.append(row)
    session.commit()
    return output


@dataclass(frozen=True)
class AlertCandidate:
    subject_type: str
    subject_id: str
    alert_type: str
    reason: str
    inputs: dict[str, object]
    score: float | None
    signal_key: str


def persist_alert(
    session: Session,
    candidate: AlertCandidate,
    *,
    now: datetime,
    cooldown_minutes: int,
    config_version: str,
    config_fingerprint: str,
) -> tuple[Alert, bool]:
    """Persist once per evidence key and suppress the same rule during cooldown."""
    dedup_key = _hash(
        {
            "subject_type": candidate.subject_type,
            "subject_id": candidate.subject_id,
            "alert_type": candidate.alert_type,
            "signal_key": candidate.signal_key,
            "config_fingerprint": config_fingerprint,
        }
    )
    exact = session.scalar(select(Alert).where(Alert.dedup_key == dedup_key))
    if exact is not None:
        return exact, False
    latest = session.scalars(
        select(Alert)
        .where(
            Alert.subject_type == candidate.subject_type,
            Alert.subject_id == candidate.subject_id,
            Alert.alert_type == candidate.alert_type,
        )
        .order_by(desc(Alert.created_at))
    ).first()
    if latest is not None and latest.cooldown_until is not None:
        cooldown_until = latest.cooldown_until
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=UTC)
        if now < cooldown_until:
            return latest, False
    row = Alert(
        id=uuid4(),
        created_at=now,
        subject_type=candidate.subject_type,
        subject_id=candidate.subject_id,
        alert_type=candidate.alert_type,
        reason=candidate.reason,
        inputs_ref={
            **candidate.inputs,
            "threshold_source": "operations_parameters",
            "method_version": "explainable-alerts-v1",
            "limitations": ["Descriptive alert; not a forecast or investment advice."],
        },
        score=candidate.score,
        status="open",
        dedup_key=dedup_key,
        cooldown_until=now + timedelta(minutes=cooldown_minutes),
        config_version=config_version,
        config_fingerprint=config_fingerprint,
    )
    session.add(row)
    session.commit()
    return row, True


def evaluate_configured_alerts(
    session: Session, now: datetime | None = None
) -> list[tuple[Alert, bool]]:
    """Evaluate every configured Step 14 rule against latest persisted evidence."""
    current_time = now or datetime.now(UTC)
    config, version, fingerprint = load_operations_config(session)
    raw_rules = config.get("alert_rules", {})
    if not isinstance(raw_rules, dict):
        raise ValueError("alert_rules must be an object")
    candidates: list[AlertCandidate] = []

    score_runs = session.scalars(
        select(ScoreRun)
        .where(ScoreRun.status == "completed", ScoreRun.run_kind == "full")
        .order_by(desc(ScoreRun.completed_at))
        .limit(2)
    ).all()
    if len(score_runs) == 2:
        latest, prior = score_runs
        latest_rows = {
            row.security_id: row
            for row in session.scalars(
                select(StockRiskResult).where(StockRiskResult.run_id == latest.id)
            ).all()
        }
        prior_rows = {
            row.security_id: row
            for row in session.scalars(
                select(StockRiskResult).where(StockRiskResult.run_id == prior.id)
            ).all()
        }
        for security_id in sorted(set(latest_rows) & set(prior_rows), key=str):
            new, old = latest_rows[security_id], prior_rows[security_id]
            risk_delta = float(new.total_score - old.total_score)
            confidence_delta = float(old.confidence - new.confidence)
            risk_threshold = float(dict(raw_rules["risk_jump"])["threshold"])
            confidence_threshold = float(dict(raw_rules["confidence_drop"])["threshold"])
            common = {
                "current_run_id": str(latest.id),
                "prior_run_id": str(prior.id),
                "effective_time": latest.as_of_date.isoformat(),
                "data_cutoff": latest.data_cutoff.isoformat(),
            }
            if risk_delta >= risk_threshold:
                candidates.append(
                    AlertCandidate(
                        "stock",
                        str(security_id),
                        "risk_jump",
                        f"Risk rose {risk_delta:.1f} points, meeting {risk_threshold:.1f}.",
                        {
                            **common,
                            "previous": float(old.total_score),
                            "current": float(new.total_score),
                            "threshold": risk_threshold,
                        },
                        risk_delta,
                        str(latest.id),
                    )
                )
            if confidence_delta >= confidence_threshold:
                candidates.append(
                    AlertCandidate(
                        "stock",
                        str(security_id),
                        "confidence_drop",
                        f"Confidence fell {confidence_delta:.1f} points, meeting "
                        f"{confidence_threshold:.1f}.",
                        {
                            **common,
                            "previous": float(old.confidence),
                            "current": float(new.confidence),
                            "threshold": confidence_threshold,
                        },
                        confidence_delta,
                        str(latest.id),
                    )
                )

    for freshness in session.scalars(
        select(DataFreshness).where(DataFreshness.status == "stale")
    ).all():
        candidates.append(
            AlertCandidate(
                "source",
                freshness.source_key,
                "stale_data",
                f"{freshness.source_key} exceeded cadence plus grace; latest success is stale.",
                {
                    "last_success_at": freshness.last_success_at.isoformat()
                    if freshness.last_success_at
                    else None,
                    "last_data_date": freshness.last_data_date.isoformat()
                    if freshness.last_data_date
                    else None,
                    "expected_cadence_minutes": freshness.expected_cadence,
                    "grace_minutes": freshness.grace,
                    "threshold": "cadence_plus_grace",
                },
                None,
                freshness.last_success_at.isoformat() if freshness.last_success_at else "never",
            )
        )

    event_threshold = float(dict(raw_rules["negative_event"])["threshold"])
    negative_events = session.execute(
        select(EventItem, TextScore)
        .join(TextScore, TextScore.item_id == EventItem.id)
        .where(TextScore.sentiment == "negative", EventItem.importance >= event_threshold)
    ).all()
    for event, text_score in negative_events:
        candidates.append(
            AlertCandidate(
                "stock",
                str(event.security_id),
                "negative_event",
                f"New negative {event.event_type} item has importance {event.importance:.1f}.",
                {
                    "event_id": str(event.id),
                    "published_at": event.published_at.isoformat(),
                    "effective_trading_date": event.effective_trading_date.isoformat(),
                    "importance": event.importance,
                    "sentiment_model": text_score.model_version,
                    "threshold": event_threshold,
                },
                event.importance,
                str(event.id),
            )
        )

    regimes = session.scalars(
        select(MarketRegime).order_by(desc(MarketRegime.as_of)).limit(2)
    ).all()
    if len(regimes) == 2 and regimes[0].regime != regimes[1].regime:
        candidates.append(
            AlertCandidate(
                "market",
                "NIFTY200",
                "regime_change",
                f"Regime changed from {regimes[1].regime} to {regimes[0].regime}.",
                {
                    "previous": regimes[1].regime,
                    "current": regimes[0].regime,
                    "as_of": regimes[0].as_of.isoformat(),
                    "threshold": "state_change",
                },
                None,
                str(regimes[0].id),
            )
        )

    mst_runs = session.scalars(
        select(MstRun)
        .where(MstRun.status == "completed")
        .order_by(desc(MstRun.computed_at))
        .limit(2)
    ).all()
    if len(mst_runs) == 2:
        held = {
            security_id
            for security_id in session.scalars(
                select(PortfolioHolding.security_id).where(
                    PortfolioHolding.security_id.is_not(None)
                )
            ).all()
            if security_id is not None
        }
        current_clusters = {
            row.security_id: row.cluster_id
            for row in session.scalars(
                select(MstCluster).where(MstCluster.run_id == mst_runs[0].id)
            ).all()
        }
        prior_clusters = {
            row.security_id: row.cluster_id
            for row in session.scalars(
                select(MstCluster).where(MstCluster.run_id == mst_runs[1].id)
            ).all()
        }
        for security_id in sorted(held & set(current_clusters) & set(prior_clusters), key=str):
            if current_clusters[security_id] != prior_clusters[security_id]:
                candidates.append(
                    AlertCandidate(
                        "stock",
                        str(security_id),
                        "mst_cluster_change",
                        "Held stock changed MST cluster; this is structural association, "
                        "not causation.",
                        {
                            "current_run_id": str(mst_runs[0].id),
                            "prior_run_id": str(mst_runs[1].id),
                            "previous_cluster": prior_clusters[security_id],
                            "current_cluster": current_clusters[security_id],
                            "threshold": "cluster_id_change",
                        },
                        None,
                        str(mst_runs[0].id),
                    )
                )

    output: list[tuple[Alert, bool]] = []
    for candidate in candidates:
        rule = raw_rules.get(candidate.alert_type, {})
        cooldown = int(dict(rule)["cooldown_minutes"])
        output.append(
            persist_alert(
                session,
                candidate,
                now=current_time,
                cooldown_minutes=cooldown,
                config_version=version,
                config_fingerprint=fingerprint,
            )
        )
    return output


def incremental_rescore(
    session: Session,
    security_id: UUID,
    parent_run_id: UUID,
    *,
    data_cutoff: datetime,
) -> CalculationSummary:
    """Create/reuse a child score run that persists only the affected security."""
    parent = session.get(ScoreRun, parent_run_id)
    if parent is None or parent.status != "completed":
        raise ValueError("parent score run must exist and be completed")
    return run_stock_score_calculation(
        session,
        parent.as_of_date,
        data_cutoff,
        config_version=parent.config_version,
        security_ids={security_id},
        parent_run_id=parent.id,
        result_limitations=[
            "Incremental filing/news rescore; prices remain end-of-day.",
        ],
    )


def list_pipeline_runs(session: Session, limit: int = 100) -> list[PipelineRun]:
    return list(
        session.scalars(
            select(PipelineRun).order_by(desc(PipelineRun.started_at)).limit(limit)
        ).all()
    )


def list_alerts(session: Session, limit: int = 100) -> list[Alert]:
    return list(session.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(limit)).all())


def list_watchlists(session: Session) -> list[WatchlistOut]:
    watchlists = session.scalars(select(Watchlist).order_by(Watchlist.name)).all()
    output: list[WatchlistOut] = []
    for watchlist in watchlists:
        rows = session.execute(
            select(WatchlistItem, SecurityAlias.symbol)
            .join(SecurityAlias, SecurityAlias.security_id == WatchlistItem.security_id)
            .where(WatchlistItem.watchlist_id == watchlist.id, SecurityAlias.valid_to.is_(None))
            .order_by(SecurityAlias.symbol)
        ).all()
        output.append(
            WatchlistOut(
                id=watchlist.id,
                name=watchlist.name,
                created_at=watchlist.created_at,
                updated_at=watchlist.updated_at,
                items=[
                    WatchlistItemOut(
                        id=item.id,
                        security_id=item.security_id,
                        symbol=symbol,
                        thresholds=dict(item.thresholds),
                    )
                    for item, symbol in rows
                ],
            )
        )
    return output


def create_watchlist(session: Session, payload: WatchlistCreate) -> WatchlistOut:
    name = payload.name.strip()
    if session.scalar(select(Watchlist).where(func.lower(Watchlist.name) == name.lower())):
        raise ValueError("watchlist name already exists")
    config, _, _ = load_operations_config(session)
    defaults = config.get("watchlist_default_thresholds", {})
    if not isinstance(defaults, dict):
        defaults = {}
    row = Watchlist(id=uuid4(), name=name)
    session.add(row)
    session.flush()
    seen: set[UUID] = set()
    for requested in payload.items:
        security_id = session.scalar(
            select(Security.id)
            .join(SecurityAlias, SecurityAlias.security_id == Security.id)
            .where(func.upper(SecurityAlias.symbol) == requested.symbol.strip().upper())
            .limit(1)
        )
        if security_id is None:
            raise ValueError(f"unknown symbol: {requested.symbol}")
        if security_id in seen:
            raise ValueError(f"duplicate symbol: {requested.symbol}")
        seen.add(security_id)
        session.add(
            WatchlistItem(
                id=uuid4(),
                watchlist_id=row.id,
                security_id=security_id,
                thresholds={**defaults, **requested.thresholds},
            )
        )
    session.commit()
    return next(item for item in list_watchlists(session) if item.id == row.id)


def delete_watchlist(session: Session, watchlist_id: UUID) -> bool:
    row = session.get(Watchlist, watchlist_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True
