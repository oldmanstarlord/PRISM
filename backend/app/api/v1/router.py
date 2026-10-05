from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.correlation_mst.service import latest_completed_mst_query
from backend.app.db.models import (
    MstEdge,
    MstNode,
    MstRun,
    PipelineRun,
    PriceDailyAdjusted,
    SectorDivergenceIssue,
    SectorDivergenceRun,
    SectorDivergenceScore,
    Security,
)
from backend.app.db.session import engine, get_session
from backend.app.fundamentals.api import router as fundamentals_router
from backend.app.portfolio.router import router as portfolio_router
from backend.app.portfolio_analytics.router import router as portfolio_analytics_router
from backend.app.sector_divergence.inputs import load_inputs
from backend.app.sector_divergence.service import (
    build_company_comparison,
    latest_completed_run_query,
    run_summary,
)

router = APIRouter()
router.include_router(fundamentals_router)
router.include_router(portfolio_router)
router.include_router(portfolio_analytics_router)
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("/status", tags=["operations"])
def project_status() -> dict[str, str]:
    return {"phase": "1", "status": "portfolio-insight"}


@router.get("/ready", tags=["operations"])
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "ready", "database": "connected"}


@router.get("/pipeline/status", tags=["operations"])
def pipeline_status(session: DatabaseSession) -> dict[str, Any]:
    """Expose publication status and freshness without treating weekends as stale."""
    latest_pipeline = session.scalar(
        select(PipelineRun)
        .where(PipelineRun.workflow == "daily_analysis")
        .order_by(desc(PipelineRun.started_at))
        .limit(1)
    )
    last_success = session.scalar(
        select(PipelineRun)
        .where(
            PipelineRun.workflow == "daily_analysis",
            PipelineRun.status == "completed",
        )
        .order_by(desc(PipelineRun.completed_at))
        .limit(1)
    )
    market_date = session.scalar(select(func.max(PriceDailyAdjusted.trade_date)))
    layer_1 = session.scalar(latest_completed_run_query())
    layer_2 = session.scalar(latest_completed_mst_query())
    layer_1_date = layer_1.signal_date if layer_1 else None
    layer_2_date = layer_2.window_end if layer_2 else None
    is_stale = (
        market_date is None
        or layer_1_date != market_date
        or layer_2_date != market_date
    )
    summary = latest_pipeline.quality_summary if latest_pipeline else {}
    return {
        "status": latest_pipeline.status if latest_pipeline else "not_run",
        "current_stage": summary.get("stage"),
        "failed_stage": (
            summary.get("stage") if latest_pipeline and latest_pipeline.status == "failed" else None
        ),
        "latest_market_date": market_date,
        "layer_1_date": layer_1_date,
        "layer_2_date": layer_2_date,
        "is_stale": is_stale,
        "last_successful_pipeline_at": last_success.completed_at if last_success else None,
        "latest_error": latest_pipeline.error_summary if latest_pipeline else None,
    }


def _latest_run(session: Session) -> SectorDivergenceRun:
    run = session.scalar(latest_completed_run_query())
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="No completed sector-divergence run is available",
        )
    return run


def _latest_mst_run(session: Session) -> MstRun:
    run = session.scalar(latest_completed_mst_query())
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="No completed correlation MST run is available",
        )
    return run


@router.get("/sector-divergence/latest", tags=["sector divergence"])
def latest_sector_divergence(session: DatabaseSession) -> dict[str, Any]:
    """Return metadata for the latest completed Layer 1 run."""
    return run_summary(_latest_run(session))


@router.get("/sector-divergence/latest/rankings", tags=["sector divergence"])
def latest_sector_divergence_rankings(
    session: DatabaseSession,
    horizon: Annotated[int, Query()] = 20,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> dict[str, Any]:
    """Rank the latest run by absolute divergence magnitude."""
    if horizon not in {1, 5, 20}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="horizon must be one of 1, 5 or 20",
        )
    run = _latest_run(session)
    scores = session.scalars(
        select(SectorDivergenceScore)
        .where(
            SectorDivergenceScore.run_id == run.id,
            SectorDivergenceScore.horizon == horizon,
        )
        .order_by(desc(func.abs(SectorDivergenceScore.divergence_value)),
                  SectorDivergenceScore.symbol)
        .limit(limit)
    ).all()
    return {
        "run": run_summary(run),
        "horizon": horizon,
        "results": [
            {
                "symbol": score.symbol,
                "industry": score.industry,
                "divergence_value": float(score.divergence_value),
                "residual_value": float(score.residual_value),
                "industry_percentile": float(score.industry_percentile),
                "interpretation": score.interpretation,
                "observations_used": score.observations_used,
                "lookback_start": score.lookback_start,
                "lookback_end": score.lookback_end,
                "adjustment_version": score.adjustment_version,
            }
            for score in scores
        ],
    }


@router.get("/sector-divergence/latest/issues", tags=["sector divergence"])
def latest_sector_divergence_issues(session: DatabaseSession) -> dict[str, Any]:
    """Return exclusions and calculation limitations for the latest run."""
    run = _latest_run(session)
    issues = session.scalars(
        select(SectorDivergenceIssue)
        .where(SectorDivergenceIssue.run_id == run.id)
        .order_by(SectorDivergenceIssue.stage, SectorDivergenceIssue.symbol,
                  SectorDivergenceIssue.horizon)
    ).all()
    return {
        "run_id": str(run.id),
        "results": [
            {
                "symbol": issue.symbol,
                "stage": issue.stage,
                "horizon": issue.horizon,
                "reason": issue.reason,
                "details": issue.details,
            }
            for issue in issues
        ],
    }


@router.get("/sector-divergence/latest/companies/{symbol}", tags=["sector divergence"])
def latest_sector_divergence_company(symbol: str, session: DatabaseSession) -> dict[str, Any]:
    """Explain one eligible company's latest scores against its exact peer benchmark."""
    normalized_symbol = symbol.strip().upper()
    run = _latest_run(session)
    scores = session.scalars(
        select(SectorDivergenceScore)
        .where(
            SectorDivergenceScore.run_id == run.id,
            SectorDivergenceScore.symbol == normalized_symbol,
        )
        .order_by(SectorDivergenceScore.horizon)
    ).all()
    if not scores:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"{normalized_symbol} has no score in the latest completed run",
        )
    security = session.get(Security, scores[0].security_id)
    inputs = load_inputs(session, run.signal_date, run.lookback_start, run.data_cutoff)
    try:
        comparison = build_company_comparison(inputs, normalized_symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return {
        "run": run_summary(run),
        "company": {
            "symbol": normalized_symbol,
            "name": security.company_name if security is not None else normalized_symbol,
            "industry": comparison.industry,
        },
        "scores": [
            {
                "horizon": score.horizon,
                "divergence_value": float(score.divergence_value),
                "residual_value": float(score.residual_value),
                "industry_percentile": float(score.industry_percentile),
                "interpretation": score.interpretation,
                "alpha": float(score.alpha),
                "beta": float(score.beta),
                "residual_volatility": float(score.residual_volatility),
                "observations_used": score.observations_used,
                "lookback_start": score.lookback_start,
                "lookback_end": score.lookback_end,
            }
            for score in scores
        ],
        "comparison": {
            "basis": "leave-one-out median daily log return of eligible industry peers",
            "indexed_to": 100,
            "peer_count": len(comparison.peer_symbols),
            "peer_symbols": comparison.peer_symbols,
            "omitted_earlier_paired_observations": comparison.omitted_observations,
            "points": [
                {
                    "trade_date": point.trade_date,
                    "stock_index": point.stock_index,
                    "benchmark_index": point.benchmark_index,
                }
                for point in comparison.points
            ],
        },
        "limitations": [
            "Daily adjusted closing prices; not live intraday data.",
            "The peer line is a statistical benchmark, not a tradeable industry index.",
            "Divergence is descriptive and does not predict reversal or continuation.",
        ],
    }


@router.get("/mst/latest", tags=["correlation MST"])
def latest_mst(session: DatabaseSession) -> dict[str, Any]:
    """Return the latest validated correlation MST with full provenance."""
    run = _latest_mst_run(session)
    nodes = session.scalars(
        select(MstNode).where(MstNode.mst_run_id == run.id).order_by(MstNode.symbol)
    ).all()
    edges = session.scalars(
        select(MstEdge).where(MstEdge.mst_run_id == run.id).order_by(MstEdge.edge_rank)
    ).all()
    return {
        "run": {
            "id": str(run.id),
            "window_start": run.window_start,
            "window_end": run.window_end,
            "data_cutoff": run.data_cutoff,
            "requested_symbol_count": run.requested_symbol_count,
            "included_symbol_count": run.included_symbol_count,
            "edge_count": run.edge_count,
            "is_connected": run.is_connected,
            "is_acyclic": run.is_acyclic,
            "implementation_version": run.implementation_version,
            "configuration": run.configuration,
            "computed_at": run.computed_at,
            "exclusions": run.exclusions.get("items", []),
        },
        "nodes": [
            {
                "id": str(node.security_id),
                "symbol": node.symbol,
                "industry": node.industry,
                "observations_used": node.observations_used,
            }
            for node in nodes
        ],
        "edges": [
            {
                "source": str(edge.security_a_id),
                "target": str(edge.security_b_id),
                "symbol_a": edge.symbol_a,
                "symbol_b": edge.symbol_b,
                "correlation": float(edge.correlation) if edge.correlation is not None else None,
                "distance": float(edge.distance),
                "paired_observations": edge.paired_observations,
                "edge_rank": edge.edge_rank,
            }
            for edge in edges
        ],
        "limitations": [
            "Correlation measures co-movement, not causation.",
            "The MST retains only N-1 relationships and omits many valid correlations.",
            "The topology can change when the lookback window or eligible universe changes.",
        ],
    }
