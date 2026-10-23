"""Read-only service for persisted structural-drift diagnostics."""

from datetime import timedelta
from typing import Any, cast

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    GnnMarketDrift,
    GnnStockDrift,
    ModelRun,
    PriceDailyAdjusted,
    SecurityAlias,
)
from backend.app.gnn.explanations import explain
from backend.app.sector_divergence.inputs import load_latest_adjusted_closes


def _explanations(session: Session, run: ModelRun, symbols: list[str]) -> dict[str, Any]:
    dates = list(
        session.scalars(
            select(GnnStockDrift.analysis_date)
            .where(GnnStockDrift.run_id == run.id)
            .distinct()
            .order_by(GnnStockDrift.analysis_date.desc())
            .limit(8)
        )
    )
    if not dates:
        return explain(symbols, [], pd.DataFrame())
    history = list(
        session.scalars(
            select(GnnStockDrift).where(
                GnnStockDrift.run_id == run.id, GnnStockDrift.analysis_date.in_(dates)
            )
        )
    )
    names = {row.symbol for row in history}
    aliases = session.execute(
        select(SecurityAlias.security_id, SecurityAlias.symbol).where(
            SecurityAlias.symbol.in_(names),
            SecurityAlias.exchange == "NSE",
            SecurityAlias.valid_from <= max(dates),
            SecurityAlias.valid_to.is_(None) | (SecurityAlias.valid_to >= max(dates)),
        )
    ).all()
    mapping = {row.security_id: row.symbol for row in aliases}
    observations = load_latest_adjusted_closes(
        session, list(mapping), max(dates) - timedelta(days=100), max(dates), run.data_cutoff
    )
    records = [
        {
            "date": row.trade_date,
            "symbol": mapping[row.security_id],
            "close": float(row.adjusted_close),
        }
        for row in observations
    ]
    prices = (
        pd.DataFrame(records).pivot(index="date", columns="symbol", values="close")
        if records
        else pd.DataFrame()
    )
    return explain(symbols, [_serialize(row) for row in history], prices)


def _latest_run(session: Session) -> ModelRun | None:
    return session.scalar(
        select(ModelRun)
        .where(ModelRun.model_name == "temporal_hetero_gnn")
        .order_by(desc(ModelRun.trained_at))
        .limit(1)
    )


def _run_meta(session: Session, run: ModelRun) -> dict[str, Any]:
    analysis_date = session.scalar(
        select(func.max(GnnMarketDrift.analysis_date)).where(GnnMarketDrift.run_id == run.id)
    )
    market_date = session.scalar(select(func.max(PriceDailyAdjusted.trade_date)))
    validation = (
        cast(dict[str, Any], run.metrics.get("drift_evaluation", {})) if run.metrics else {}
    )
    production_eligible = bool(validation.get("production_eligible", False))
    stale = bool(
        analysis_date is None
        or (market_date is not None and (market_date - analysis_date).days > 10)
    )
    return {
        "run_id": str(run.id),
        "model_version": run.model_version,
        "methodology_version": run.methodology_version,
        "status": "stale" if stale else "ready" if production_eligible else "research_only",
        "production_eligible": production_eligible,
        "analysis_date": analysis_date,
        "latest_market_date": market_date,
        "is_stale": stale,
        "data_cutoff": run.data_cutoff,
        "training_window": [run.training_window_start, run.training_window_end],
        "test_window": [run.test_window_start, run.test_window_end],
        "selection_reason": run.selection_reason,
        "validation": validation,
    }


def status(session: Session) -> dict[str, Any]:
    run = _latest_run(session)
    if run is None:
        return {
            "status": "unavailable",
            "production_eligible": False,
            "selection_reason": "No persisted GNN analysis is available.",
        }
    return _run_meta(session, run)


def _serialize(row: GnnStockDrift) -> dict[str, Any]:
    return {
        "date": row.analysis_date,
        "symbol": row.symbol,
        "industry": row.industry,
        "embedding_drift": float(row.embedding_drift),
        "drift_percentile": float(row.drift_percentile),
        "alert_level": row.alert_level,
        "primary_driver": row.primary_driver,
        "driver_scope": row.driver_scope,
        "driver_scores": row.driver_scores,
        "explanation": row.explanation,
    }


def portfolio_drift(session: Session, symbols: list[str]) -> dict[str, Any]:
    run = _latest_run(session)
    if run is None:
        return {"run": status(session), "results": []}
    latest = session.scalar(
        select(func.max(GnnStockDrift.analysis_date)).where(GnnStockDrift.run_id == run.id)
    )
    rows = (
        session.scalars(
            select(GnnStockDrift)
            .where(
                GnnStockDrift.run_id == run.id,
                GnnStockDrift.analysis_date == latest,
                GnnStockDrift.symbol.in_(symbols),
            )
            .order_by(desc(GnnStockDrift.drift_percentile), GnnStockDrift.symbol)
        ).all()
        if latest
        else []
    )
    return {
        "run": _run_meta(session, run),
        "results": [_serialize(row) for row in rows],
        "explainability": _explanations(session, run, symbols),
        "missing_symbols": sorted(set(symbols) - {row.symbol for row in rows}),
        "limitations": [
            "Structural drift is descriptive and is not a probability of loss.",
            "Observed drivers are diagnostics, not causal attributions.",
            "No price direction or trading action is inferred.",
        ],
    }


def company_history(session: Session, symbol: str, limit: int = 52) -> dict[str, Any]:
    run = _latest_run(session)
    if run is None:
        return {"run": status(session), "symbol": symbol, "history": []}
    rows = session.scalars(
        select(GnnStockDrift)
        .where(GnnStockDrift.run_id == run.id, GnnStockDrift.symbol == symbol)
        .order_by(desc(GnnStockDrift.analysis_date))
        .limit(limit)
    ).all()
    return {
        "run": _run_meta(session, run),
        "symbol": symbol,
        "latest": _serialize(rows[0]) if rows else None,
        "history": [_serialize(row) for row in reversed(rows)],
    }


def market_history(session: Session, limit: int = 52) -> dict[str, Any]:
    run = _latest_run(session)
    if run is None:
        return {"run": status(session), "history": []}
    rows = session.scalars(
        select(GnnMarketDrift)
        .where(GnnMarketDrift.run_id == run.id)
        .order_by(desc(GnnMarketDrift.analysis_date))
        .limit(limit)
    ).all()
    return {
        "run": _run_meta(session, run),
        "history": [
            {
                "date": row.analysis_date,
                "mean_drift": float(row.mean_drift),
                "share_above_train_95pct": float(row.share_above_train_95pct),
                "active_stocks": row.active_stocks,
            }
            for row in reversed(rows)
        ],
    }
