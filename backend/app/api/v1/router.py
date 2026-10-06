from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.correlation_mst.service import latest_completed_mst_query
from backend.app.data_sources.coverage import build_data_coverage
from backend.app.data_sources.schemas import DataCoverageOut, DataSourceOut
from backend.app.data_sources.service import list_data_sources
from backend.app.db.models import (
    BenchmarkSeries,
    DataCrosscheck,
    ModelConfig,
    MstCluster,
    MstEdge,
    MstNode,
    MstNodeMetric,
    MstRun,
    MstStability,
    PriceDailyAdjusted,
    PriceDailyRaw,
    ScoreComponentDefinition,
    SectorDivergenceIssue,
    SectorDivergenceRun,
    SectorDivergenceScore,
    Security,
    SecurityMarketStat,
    SecurityShareCount,
)
from backend.app.db.session import engine, get_session
from backend.app.events.schemas import RecentEventsResponse, StockEventsResponse
from backend.app.explain.schemas import (
    ExplanationPayload,
    ExplanationSearchResult,
    ExplanationSummaryOut,
    GlossaryTermOut,
)
from backend.app.explain.sector import SectorOverviewResponse, build_sector_overview
from backend.app.explain.service import (
    get_glossary_term,
    get_or_create_alert_explanation,
    get_or_create_component_explanation,
    get_or_create_divergence_explanation,
    get_or_create_diversification_explanation,
    get_or_create_mst_edge_explanation,
    get_or_create_mst_node_explanation,
    get_or_create_mst_pair_explanation,
    get_or_create_news_explanation,
    get_or_create_score_change_explanation,
    get_or_create_sector_explanation,
    get_or_create_shock_explanation,
    list_glossary,
    list_recent_explanations,
    load_explain_config,
    search_explanations,
)
from backend.app.fundamentals.service import get_stock_fundamentals
from backend.app.macro.schemas import (
    MacroSeriesDefinitionOut,
    MacroSeriesDetailOut,
    MarketRegimeOut,
    SectorMacroSensitivityOut,
    StockMacroExposureOut,
)
from backend.app.mst_diagnostics.config import load_mst_diagnostics_config
from backend.app.mst_diagnostics.stability import calculate_stability_grade
from backend.app.news_impact.schemas import NewsInsightsResponse, PortfolioNewsOverlayOut
from backend.app.news_impact.service import get_portfolio_news_overlay, list_news_insights
from backend.app.operations.schemas import (
    AlertOut,
    FreshnessOut,
    LimitationsOut,
    PipelineRunOut,
    WatchlistCreate,
    WatchlistOut,
)
from backend.app.operations.service import (
    create_watchlist,
    delete_watchlist,
    evaluate_freshness,
    list_alerts,
    list_pipeline_runs,
    list_watchlists,
    load_operations_config,
)
from backend.app.policy.schemas import (
    PolicyRuleOut,
    PolicyRuleUpdate,
    RecentPolicyEventsResponse,
    StockNewsResponse,
)
from backend.app.portfolio import service as portfolio_service
from backend.app.portfolio.schemas import (
    DiversificationResponse,
    PortfolioCreate,
    PortfolioImportResult,
    PortfolioOut,
    PortfolioRiskRunOut,
    PortfolioRiskScoreOut,
    RiskRunRequest,
    RowValidationError,
    ShockRequest,
    ShockScenarioResponse,
)
from backend.app.risk_score.registry import registry
from backend.app.risk_score.service import (
    get_latest_stock_scores,
    get_stock_risk_envelope,
    get_stock_risk_history,
)
from backend.app.sector_divergence.inputs import load_inputs
from backend.app.sector_divergence.service import (
    build_company_comparison,
    latest_completed_run_query,
    run_summary,
)
from backend.app.validation.schemas import ValidationRunDetailOut, ValidationRunSummaryOut
from backend.app.validation.service import get_validation_run, list_validation_runs

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("/data/sources", response_model=list[DataSourceOut], tags=["data quality"])
def data_sources(session: DatabaseSession) -> list[DataSourceOut]:
    """List live, manual, TBD, and disabled datasets with their visible status."""
    return list_data_sources(session)


@router.get("/data/coverage", response_model=DataCoverageOut, tags=["data quality"])
def data_coverage(session: DatabaseSession) -> DataCoverageOut:
    """Return row/date/universe and risk-dimension coverage from permitted real sources."""
    return build_data_coverage(session)


@router.get("/news/insights", response_model=NewsInsightsResponse, tags=["news"])
def news_insights(
    session: DatabaseSession,
    industry: str | None = None,
    severity: Annotated[float | None, Query(ge=0, le=10)] = None,
    portfolio_id: UUID | None = None,
) -> NewsInsightsResponse:
    """List evidence-backed news impacts from allowlisted live sources only."""
    return list_news_insights(session, industry, severity, portfolio_id)


@router.get(
    "/explain/news/{news_id}",
    response_model=ExplanationPayload,
    tags=["explanations", "news"],
)
def explain_news(news_id: UUID, session: DatabaseSession) -> ExplanationPayload:
    try:
        return get_or_create_news_explanation(session, news_id)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/explain/portfolio/{portfolio_id}/news/{news_id}",
    response_model=PortfolioNewsOverlayOut,
    tags=["explanations", "news", "portfolio"],
)
def explain_portfolio_news(
    portfolio_id: UUID, news_id: UUID, session: DatabaseSession
) -> PortfolioNewsOverlayOut:
    try:
        return get_portfolio_news_overlay(session, portfolio_id, news_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/explain/component/{symbol}/{component_key}",
    response_model=ExplanationPayload,
    tags=["explanations"],
)
def explain_component(
    symbol: str,
    component_key: str,
    session: DatabaseSession,
    as_of: date | None = None,
) -> ExplanationPayload:
    """Return or reuse a deterministic explanation of one stored component value."""
    try:
        payload, _, _ = get_or_create_component_explanation(
            session, symbol, component_key, as_of=as_of
        )
        return payload
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/explain/divergence/{symbol}",
    response_model=ExplanationPayload,
    tags=["explanations"],
)
def explain_divergence(
    symbol: str,
    session: DatabaseSession,
    as_of: date | None = None,
) -> ExplanationPayload:
    try:
        return get_or_create_divergence_explanation(session, symbol, as_of)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/explain/sector/{industry}",
    response_model=ExplanationPayload,
    tags=["explanations"],
)
def explain_sector(
    industry: str,
    session: DatabaseSession,
    as_of: date | None = None,
) -> ExplanationPayload:
    try:
        return get_or_create_sector_explanation(session, industry, as_of)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/sectors/overview",
    response_model=SectorOverviewResponse,
    tags=["sector divergence"],
)
def sectors_overview(
    session: DatabaseSession,
    as_of: date | None = None,
) -> SectorOverviewResponse:
    try:
        return build_sector_overview(session, as_of)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/glossary", response_model=list[GlossaryTermOut], tags=["explanations"])
def glossary(session: DatabaseSession) -> list[GlossaryTermOut]:
    return list_glossary(session)


@router.get("/glossary/{term}", response_model=GlossaryTermOut, tags=["explanations"])
def glossary_term(term: str, session: DatabaseSession) -> GlossaryTermOut:
    result = get_glossary_term(session, term)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Glossary term '{term}' not found")
    return result


@router.get("/explain/mst/edge", response_model=ExplanationPayload, tags=["explanations"])
def explain_mst_edge(
    session: DatabaseSession,
    run_id: UUID,
    a: str = Query(min_length=1),
    b: str = Query(min_length=1),
    portfolio_id: UUID | None = None,
) -> ExplanationPayload:
    if a.upper() == b.upper():
        raise HTTPException(status_code=400, detail="a and b must be different symbols")
    try:
        return get_or_create_mst_edge_explanation(session, run_id, a, b, portfolio_id)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/explain/mst/node/{symbol}", response_model=ExplanationPayload, tags=["explanations"])
def explain_mst_node(
    symbol: str,
    session: DatabaseSession,
    as_of: date | None = None,
    portfolio_id: UUID | None = None,
) -> ExplanationPayload:
    try:
        return get_or_create_mst_node_explanation(session, symbol, as_of, portfolio_id)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/explain/mst/pair", response_model=ExplanationPayload, tags=["explanations"])
def explain_mst_pair(
    session: DatabaseSession,
    a: str = Query(min_length=1),
    b: str = Query(min_length=1),
    as_of: date | None = None,
    portfolio_id: UUID | None = None,
) -> ExplanationPayload:
    if a.upper() == b.upper():
        raise HTTPException(status_code=400, detail="a and b must be different symbols")
    try:
        return get_or_create_mst_pair_explanation(session, a, b, as_of, portfolio_id)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/explain/shock", response_model=ExplanationPayload, tags=["explanations", "shock"])
def explain_shock(
    session: DatabaseSession,
    holding_symbol: str = Query(min_length=1),
    shocked_symbol: str = Query(min_length=1),
    portfolio_id: UUID | None = None,
    scenario_id: UUID | None = None,
    shock_pct: float = Query(default=-10.0),
    method: str = Query(default="regression_beta"),
) -> ExplanationPayload:
    try:
        return get_or_create_shock_explanation(
            session,
            holding_symbol=holding_symbol,
            shocked_symbol=shocked_symbol,
            portfolio_id=portfolio_id,
            scenario_id=scenario_id,
            shock_pct=shock_pct,
            method=method,
        )[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/explain/diversification/{portfolio_id}",
    response_model=ExplanationPayload,
    tags=["explanations", "diversification"],
)
def explain_diversification(
    portfolio_id: UUID,
    session: DatabaseSession,
    run_id: UUID | None = None,
    as_of: date | None = None,
) -> ExplanationPayload:
    try:
        return get_or_create_diversification_explanation(
            session, portfolio_id=portfolio_id, run_id=run_id, as_of=as_of
        )[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/explain/score-change/{symbol}",
    response_model=ExplanationPayload,
    tags=["explanations", "score_change"],
)
def explain_score_change(
    symbol: str,
    session: DatabaseSession,
    as_of: date | None = None,
) -> ExplanationPayload:
    try:
        return get_or_create_score_change_explanation(session, symbol, as_of=as_of)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/explain/alert/{alert_id}",
    response_model=ExplanationPayload,
    tags=["explanations", "alerts"],
)
def explain_alert(
    alert_id: UUID,
    session: DatabaseSession,
) -> ExplanationPayload:
    try:
        return get_or_create_alert_explanation(session, alert_id)[0]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/explain/recent",
    response_model=list[ExplanationSummaryOut],
    tags=["explanations"],
)
def explain_recent(
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ExplanationSummaryOut]:
    return list_recent_explanations(session, limit)


@router.get(
    "/explain/search",
    response_model=list[ExplanationSearchResult],
    tags=["explanations"],
)
def explain_search(
    session: DatabaseSession,
    q: str = Query(default="", min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ExplanationSearchResult]:
    return search_explanations(session, q, limit)


@router.get("/ops/pipeline-runs", response_model=list[PipelineRunOut], tags=["operations"])
def operations_pipeline_runs(
    session: DatabaseSession, limit: int = Query(default=100, ge=1, le=500)
) -> list[PipelineRunOut]:
    return [PipelineRunOut.model_validate(row) for row in list_pipeline_runs(session, limit)]


@router.get("/ops/freshness", response_model=list[FreshnessOut], tags=["operations"])
def operations_freshness(session: DatabaseSession) -> list[FreshnessOut]:
    return [FreshnessOut.model_validate(row) for row in evaluate_freshness(session)]


@router.get("/alerts", response_model=list[AlertOut], tags=["alerts"])
def alerts_list(
    session: DatabaseSession, limit: int = Query(default=100, ge=1, le=500)
) -> list[AlertOut]:
    return [AlertOut.model_validate(row) for row in list_alerts(session, limit)]


@router.post(
    "/watchlists",
    response_model=WatchlistOut,
    status_code=http_status.HTTP_201_CREATED,
    tags=["watchlists"],
)
def watchlist_create(payload: WatchlistCreate, session: DatabaseSession) -> WatchlistOut:
    try:
        return create_watchlist(session, payload)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/watchlists", response_model=list[WatchlistOut], tags=["watchlists"])
def watchlists_list(session: DatabaseSession) -> list[WatchlistOut]:
    return list_watchlists(session)


@router.delete(
    "/watchlists/{watchlist_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    tags=["watchlists"],
)
def watchlist_delete(watchlist_id: UUID, session: DatabaseSession) -> None:
    if not delete_watchlist(session, watchlist_id):
        raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")


@router.get("/about/limitations", response_model=LimitationsOut, tags=["operations"])
def limitations(session: DatabaseSession) -> LimitationsOut:
    config, _, _ = load_operations_config(session)
    return LimitationsOut(
        method_version="operations-disclosure-v1",
        price_frequency_label=str(config["price_frequency_label"]),
        filings_news_poll_minutes=int(config["near_real_time_poll_minutes"]),
        limitations=[str(item) for item in config.get("limitations", [])],
    )


@router.get("/validation/runs", response_model=list[ValidationRunSummaryOut], tags=["validation"])
def validation_runs(session: DatabaseSession) -> list[ValidationRunSummaryOut]:
    """List persisted honest-validation runs, including failed outcomes."""
    return list_validation_runs(session)


@router.get(
    "/validation/runs/{run_id}",
    response_model=ValidationRunDetailOut,
    tags=["validation"],
)
def validation_run_detail(run_id: UUID, session: DatabaseSession) -> ValidationRunDetailOut:
    """Return metrics, baselines, ablations, calibration, and limitations for one run."""
    try:
        return get_validation_run(session, run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Validation run {run_id} not found",
        ) from exc


@router.get("/status", tags=["operations"])
def project_status() -> dict[str, str]:
    return {"phase": "0", "status": "foundation"}


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


def _latest_run(session: Session) -> SectorDivergenceRun:
    run = session.scalar(latest_completed_run_query())
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="No completed sector-divergence run is available",
        )
    return run


def _latest_mst_run(session: Session, variant: str = "raw") -> MstRun:
    runs = session.scalars(
        select(MstRun)
        .where(MstRun.status == "completed")
        .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
    ).all()
    for r in runs:
        r_var = (r.configuration or {}).get("variant", "raw")
        if r_var == variant:
            return r
    raise HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail=f"No completed correlation MST run is available for variant '{variant}'",
    )


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
        .order_by(
            desc(func.abs(SectorDivergenceScore.divergence_value)), SectorDivergenceScore.symbol
        )
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
        .order_by(
            SectorDivergenceIssue.stage, SectorDivergenceIssue.symbol, SectorDivergenceIssue.horizon
        )
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
def latest_mst(
    session: DatabaseSession,
    variant: Annotated[str, Query(pattern="^(raw|residual)$")] = "raw",
) -> dict[str, Any]:
    """Return latest validated correlation MST with provenance and diagnostic enrichment."""
    run = _latest_mst_run(session, variant=variant)
    nodes = session.scalars(
        select(MstNode).where(MstNode.mst_run_id == run.id).order_by(MstNode.symbol)
    ).all()
    edges = session.scalars(
        select(MstEdge).where(MstEdge.mst_run_id == run.id).order_by(MstEdge.edge_rank)
    ).all()

    # Diagnostic annotations
    metrics_map = {
        m.symbol: m
        for m in session.scalars(select(MstNodeMetric).where(MstNodeMetric.run_id == run.id)).all()
    }
    clusters_map = {
        c.symbol: c.cluster_id
        for c in session.scalars(select(MstCluster).where(MstCluster.run_id == run.id)).all()
    }
    stability_row = session.scalar(
        select(MstStability).where(MstStability.run_id == run.id).limit(1)
    )

    cfg = load_mst_diagnostics_config(session)
    grade = (
        calculate_stability_grade(
            float(stability_row.edge_persistence),
            cfg.threshold_high,
            cfg.threshold_medium,
        )
        if stability_row is not None
        else None
    )
    try:
        explain_config = load_explain_config(session, "1.2.0", "mst_explain_templates")[0]
        distance_scale = explain_config.get("distance_scale", [])
    except LookupError:
        distance_scale = []

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
            "variant": variant,
        },
        "variant": variant,
        "stability_grade": grade,
        "edge_persistence": float(stability_row.edge_persistence)
        if stability_row is not None
        else None,
        "clusters_count": len(set(clusters_map.values())) if clusters_map else None,
        "distance_scale": distance_scale,
        "edge_thickness_legend": [
            {"correlation": -1.0, "width": 0.6},
            {"correlation": 0.0, "width": 2.05},
            {"correlation": 1.0, "width": 3.5},
        ],
        "nodes": [
            {
                "id": str(node.security_id),
                "symbol": node.symbol,
                "industry": node.industry,
                "observations_used": node.observations_used,
                "degree": metrics_map[node.symbol].degree if node.symbol in metrics_map else None,
                "weighted_centrality": float(metrics_map[node.symbol].weighted_centrality)
                if node.symbol in metrics_map
                else None,
                "hub_rank": metrics_map[node.symbol].hub_rank
                if node.symbol in metrics_map
                else None,
                "cluster_id": clusters_map.get(node.symbol),
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
            "The MST retains only N-1 relationships and omits many valid pairwise co-movements.",
            "The topology can change when the lookback window or eligible universe changes.",
            "Edges are a sparse subset of all pairwise co-movements.",
        ],
    }


@router.get("/mst/stability/latest", tags=["correlation MST"])
def latest_mst_stability(
    session: DatabaseSession,
    variant: Annotated[str, Query(pattern="^(raw|residual)$")] = "raw",
) -> dict[str, Any]:
    """Retrieve edge persistence, node overlap, and stability grade for latest MST transition."""
    run = _latest_mst_run(session, variant=variant)
    cfg = load_mst_diagnostics_config(session)

    stability = session.scalar(select(MstStability).where(MstStability.run_id == run.id).limit(1))

    all_stabilities = session.scalars(
        select(MstStability)
        .join(MstRun, MstStability.run_id == MstRun.id)
        .order_by(desc(MstRun.window_end))
    ).all()
    matched_stabs = [
        s
        for s in all_stabilities
        if (session.get(MstRun, s.run_id) is not None)
        and (session.get(MstRun, s.run_id).configuration or {}).get("variant", "raw") == variant  # type: ignore[union-attr]
    ]

    persistences = [float(s.edge_persistence) for s in matched_stabs]
    avg_p = round(sum(persistences) / len(persistences), 4) if persistences else 0.0
    worst_p = round(min(persistences), 4) if persistences else 0.0

    worst_window_dates: list[str] | None = None
    if matched_stabs:
        worst_item = min(matched_stabs, key=lambda s: float(s.edge_persistence))
        worst_run_obj = session.get(MstRun, worst_item.run_id)
        if worst_run_obj is not None:
            worst_window_dates = [
                worst_run_obj.window_start.isoformat(),
                worst_run_obj.window_end.isoformat(),
            ]

    latest_summary: dict[str, Any] | None = None
    if stability is not None:
        p_val = float(stability.edge_persistence)
        grade = calculate_stability_grade(p_val, cfg.threshold_high, cfg.threshold_medium)
        latest_summary = {
            "run_id": str(stability.run_id),
            "prior_run_id": str(stability.prior_run_id),
            "edge_persistence": p_val,
            "node_overlap": float(stability.node_overlap),
            "window_gap_days": stability.window_gap_days,
            "grade": grade,
            "details": stability.details,
        }

    return {
        "variant": variant,
        "latest_stability": latest_summary,
        "history_summary": {
            "windows_evaluated": len(matched_stabs),
            "average_edge_persistence": avg_p,
            "worst_edge_persistence": worst_p,
            "worst_window": worst_window_dates,
            "thresholds": {"high": cfg.threshold_high, "medium": cfg.threshold_medium},
        },
        "default_variant": cfg.default_variant,
        "limitations": [
            "Stability measures edge persistence across rolling windows, not reliability.",
            "High persistence does not imply economic permanence or causal relations.",
            "Universe exclusions and corporate actions inherently produce edge turnover.",
        ],
    }


@router.get("/mst/clusters/latest", tags=["correlation MST"])
def latest_mst_clusters(
    session: DatabaseSession,
    variant: Annotated[str, Query(pattern="^(raw|residual)$")] = "raw",
) -> dict[str, Any]:
    """Retrieve deterministic clusters formed by removing the k-longest MST edges."""
    run = _latest_mst_run(session, variant=variant)
    cfg = load_mst_diagnostics_config(session)
    clusters = session.scalars(
        select(MstCluster)
        .where(MstCluster.run_id == run.id)
        .order_by(MstCluster.cluster_id, MstCluster.symbol)
    ).all()

    grouped: dict[str, list[str]] = {}
    for c in clusters:
        if c.cluster_id not in grouped:
            grouped[c.cluster_id] = []
        grouped[c.cluster_id].append(c.symbol)

    return {
        "run_id": str(run.id),
        "variant": variant,
        "cluster_rule_version": cfg.cluster_rule_version,
        "cluster_k_cut": cfg.cluster_k_cut,
        "clusters_count": len(grouped),
        "clusters": grouped,
        "members": [
            {
                "security_id": str(c.security_id),
                "symbol": c.symbol,
                "cluster_id": c.cluster_id,
                "cluster_size": c.cluster_size,
                "cluster_rule_version": c.cluster_rule_version,
            }
            for c in clusters
        ],
        "limitations": [
            "Clusters are formed deterministically by cutting the k longest edges of the MST.",
            "Clusters represent co-movement subgraphs, not fundamental industrial classifications.",
            "A stock outside a cluster may still have pairwise correlation with its members.",
        ],
    }


@router.get("/mst/nodes/{symbol}/metrics", tags=["correlation MST"])
def get_mst_node_metrics(
    symbol: str,
    session: DatabaseSession,
    variant: Annotated[str, Query(pattern="^(raw|residual)$")] = "raw",
) -> dict[str, Any]:
    """Retrieve degree, weighted centrality, hub rank, and cluster peers for a given symbol."""
    norm_symbol = symbol.strip().upper()
    run = _latest_mst_run(session, variant=variant)

    metric = session.scalar(
        select(MstNodeMetric).where(
            MstNodeMetric.run_id == run.id,
            MstNodeMetric.symbol == norm_symbol,
        )
    )
    if metric is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{norm_symbol}' has no metrics in the latest {variant} MST run",
        )

    cluster = session.scalar(
        select(MstCluster).where(
            MstCluster.run_id == run.id,
            MstCluster.symbol == norm_symbol,
        )
    )

    cluster_peers: list[str] = []
    if cluster is not None:
        cluster_peers = [
            c.symbol
            for c in session.scalars(
                select(MstCluster)
                .where(
                    MstCluster.run_id == run.id,
                    MstCluster.cluster_id == cluster.cluster_id,
                    MstCluster.symbol != norm_symbol,
                )
                .order_by(MstCluster.symbol)
            ).all()
        ]

    # Find incident edges
    edges = session.scalars(
        select(MstEdge)
        .where(
            MstEdge.mst_run_id == run.id,
            (MstEdge.symbol_a == norm_symbol) | (MstEdge.symbol_b == norm_symbol),
        )
        .order_by(MstEdge.edge_rank)
    ).all()

    incident_edges = [
        {
            "neighbor_symbol": e.symbol_b if e.symbol_a == norm_symbol else e.symbol_a,
            "correlation": float(e.correlation) if e.correlation is not None else None,
            "distance": float(e.distance),
            "edge_rank": e.edge_rank,
            "paired_observations": e.paired_observations,
        }
        for e in edges
    ]

    return {
        "security_id": str(metric.security_id),
        "symbol": norm_symbol,
        "run_id": str(run.id),
        "variant": variant,
        "degree": metric.degree,
        "weighted_centrality": float(metric.weighted_centrality),
        "hub_rank": metric.hub_rank,
        "cluster_id": cluster.cluster_id if cluster else None,
        "cluster_size": cluster.cluster_size if cluster else None,
        "cluster_peers": cluster_peers,
        "incident_edges": incident_edges,
        "limitations": [
            "Degree and weighted centrality reflect tree connectivity, not systemic importance.",
            "Hub positions summarize correlation networks descriptively and are not causal.",
        ],
    }


@router.get("/config/models", tags=["configuration"])
def list_model_configs(
    session: DatabaseSession,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """List versioned model configurations with their hashes and approval states."""
    stmt = select(ModelConfig)
    if status is not None:
        stmt = stmt.where(ModelConfig.status == status)
    stmt = stmt.order_by(ModelConfig.config_key, ModelConfig.version.desc())
    rows = session.scalars(stmt).all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": str(row.id),
                "config_key": row.config_key,
                "version": row.version,
                "status": row.status,
                "configuration": row.configuration,
                "configuration_hash": row.configuration_hash,
                "approved_at": row.approved_at,
                "approved_by": row.approved_by,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
    }


@router.get("/config/components", tags=["configuration"])
def list_score_components(
    session: DatabaseSession,
    dimension: Annotated[str | None, Query()] = None,
    active_only: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """List registered risk score components and their metadata (D2)."""
    # Try loading from database first; fallback to memory registry if DB table empty
    try:
        stmt = select(ScoreComponentDefinition)
        if dimension is not None:
            stmt = stmt.where(ScoreComponentDefinition.dimension == dimension)
        if active_only:
            stmt = stmt.where(ScoreComponentDefinition.active.is_(True))
        stmt = stmt.order_by(
            ScoreComponentDefinition.dimension, ScoreComponentDefinition.component_id
        )
        rows = session.scalars(stmt).all()
        if rows:
            return {
                "count": len(rows),
                "source": "database",
                "items": [
                    {
                        "id": str(row.id),
                        "component_id": row.component_id,
                        "dimension": row.dimension,
                        "name": row.name,
                        "description": row.description,
                        "direction": row.direction,
                        "scope": row.scope,
                        "min_group_size": row.min_group_size,
                        "weight": float(row.weight),
                        "active": row.active,
                        "introduced_in_step": row.introduced_in_step,
                    }
                    for row in rows
                ],
            }
    except Exception:
        pass

    # Fallback to in-memory registry
    items = registry.list_components(dimension=dimension, active_only=active_only)
    return {
        "count": len(items),
        "source": "registry",
        "items": [
            {
                "id": str(item.id) if item.id else None,
                "component_id": item.component_id,
                "dimension": item.dimension,
                "name": item.name,
                "description": item.description,
                "direction": item.direction,
                "scope": item.scope,
                "min_group_size": item.min_group_size,
                "weight": item.weight,
                "active": item.active,
                "introduced_in_step": item.introduced_in_step,
            }
            for item in items
        ],
    }


@router.get("/meta", tags=["operations"])
def get_system_metadata(session: DatabaseSession) -> dict[str, Any]:
    """Return platform metadata, compliance disclaimers, universe info, and active configs."""
    # Check latest Layer 1 run
    l1_run = session.scalar(latest_completed_run_query())
    l1_summary = run_summary(l1_run) if l1_run is not None else None

    # Check latest Layer 2 MST run
    mst_run = session.scalar(latest_completed_mst_query())
    mst_summary = (
        {
            "run_id": str(mst_run.id),
            "window_end": mst_run.window_end.isoformat(),
            "included_symbol_count": mst_run.included_symbol_count,
            "edge_count": mst_run.edge_count,
            "is_connected": mst_run.is_connected,
            "is_acyclic": mst_run.is_acyclic,
        }
        if mst_run is not None
        else None
    )

    # Active config versions
    configs = session.scalars(
        select(ModelConfig).order_by(ModelConfig.config_key, ModelConfig.version.desc())
    ).all()
    config_versions: dict[str, dict[str, Any]] = {}
    for c in configs:
        if c.config_key not in config_versions:
            config_versions[c.config_key] = {
                "version": c.version,
                "status": c.status,
                "hash": c.configuration_hash,
            }

    disclaimer_text = (
        "PRISM is descriptive risk and explanation, NOT price prediction and NOT "
        "investment advice. No look-ahead anywhere. Every score, alert, forecast and "
        "scenario must show reason, inputs, thresholds, method version, data age and "
        "limitations. MST/correlation is never presented as causal. Shock simulation is "
        "a scenario, not a forecast."
    )

    return {
        "platform": "PRISM",
        "authority": "PRISM_SRS.md",
        "disclaimer": disclaimer_text,
        "universe": "NIFTY 200",
        "latest_pipeline_runs": {
            "sector_divergence": l1_summary,
            "correlation_mst": mst_summary,
        },
        "config_versions": config_versions,
    }


@router.get("/data/quality/summary", tags=["data quality"])
def data_quality_summary(session: DatabaseSession) -> dict[str, Any]:
    """Summary of data quality and issue counts across ingested and derived datasets (NFR-9)."""
    raw_count = session.scalar(select(func.count(PriceDailyRaw.id))) or 0
    adj_count = session.scalar(select(func.count(PriceDailyAdjusted.id))) or 0
    bench_count = session.scalar(select(func.count(BenchmarkSeries.id))) or 0
    stats_count = session.scalar(select(func.count(SecurityMarketStat.id))) or 0

    # Thin trading / zero volume stats count
    thin_count = (
        session.scalar(
            select(func.count(SecurityMarketStat.id)).where(
                SecurityMarketStat.flags.op("->>")("thin_trading") == "true"
            )
        )
        or 0
    )

    return {
        "datasets": {
            "price_daily_raw": {"total_rows": raw_count},
            "price_daily_adjusted": {"total_rows": adj_count},
            "benchmark_series": {"total_rows": bench_count},
            "security_market_stat": {
                "total_rows": stats_count,
                "thin_trading_flagged": thin_count,
            },
        },
        "quality_policy": (
            "PRISM SRS Section 7.6 (reject invalid, flag suspicious, never overwrite)"
        ),
    }


@router.get("/data/freshness", tags=["data quality"])
def data_freshness(session: DatabaseSession) -> dict[str, Any]:
    """Return latest available trade date and data age across each dataset."""
    latest_raw = session.scalar(select(func.max(PriceDailyRaw.trade_date)))
    latest_adj = session.scalar(select(func.max(PriceDailyAdjusted.trade_date)))
    latest_bench = session.scalar(select(func.max(BenchmarkSeries.trade_date)))
    latest_stat = session.scalar(select(func.max(SecurityMarketStat.trade_date)))
    latest_shares = session.scalar(select(func.max(SecurityShareCount.as_of)))

    return {
        "datasets": {
            "price_daily_raw": latest_raw.isoformat() if latest_raw else None,
            "price_daily_adjusted": latest_adj.isoformat() if latest_adj else None,
            "benchmark_series": latest_bench.isoformat() if latest_bench else None,
            "security_market_stat": latest_stat.isoformat() if latest_stat else None,
            "security_share_count": latest_shares.isoformat() if latest_shares else None,
        }
    }


@router.get("/data/crosscheck/latest", tags=["data quality"])
def latest_crosscheck(session: DatabaseSession) -> dict[str, Any]:
    """Return the most recent price cross-check run results and mismatch rates."""
    latest_run_id = session.scalar(
        select(DataCrosscheck.run_id).order_by(DataCrosscheck.checked_at.desc()).limit(1)
    )
    if latest_run_id is None:
        return {
            "status": "no_runs",
            "message": "No price cross-check runs have been executed yet.",
        }

    rows = session.scalars(
        select(DataCrosscheck).where(DataCrosscheck.run_id == latest_run_id)
    ).all()

    total = len(rows)
    matches = sum(1 for r in rows if r.status == "match")
    mismatches = sum(1 for r in rows if r.status == "mismatch")
    missing_b = sum(1 for r in rows if r.status == "missing_b")
    mismatch_rate = (
        round(mismatches / (matches + mismatches), 4) if (matches + mismatches) > 0 else 0.0
    )

    worst = [
        {
            "security_id": str(r.security_id),
            "trade_date": r.trade_date.isoformat(),
            "close_a": float(r.close_a),
            "close_b": float(r.close_b),
            "rel_diff": float(r.rel_diff),
            "status": r.status,
        }
        for r in sorted(rows, key=lambda x: x.rel_diff, reverse=True)[:10]
    ]

    return {
        "run_id": str(latest_run_id),
        "total_checked": total,
        "matches": matches,
        "mismatches": mismatches,
        "missing_comparison": missing_b,
        "mismatch_rate": mismatch_rate,
        "worst_offenders": worst,
    }


# ============================================================================
# Step 3: Portfolio Engine Endpoints (SRS FR-P1, FR-R1 to FR-R7)
# ============================================================================


@router.post("/portfolios", response_model=PortfolioOut, tags=["portfolio"])
def create_portfolio(
    payload: PortfolioCreate,
    session: DatabaseSession,
) -> PortfolioOut:
    """Create a new portfolio with initial positions and weights."""
    return portfolio_service.create_portfolio(session, payload)


@router.post(
    "/portfolios/import-csv",
    response_model=PortfolioImportResult,
    tags=["portfolio"],
)
async def import_portfolio_csv(
    request: Request,
    session: DatabaseSession,
) -> PortfolioImportResult:
    """Import portfolio holdings from CSV with row-level validation."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        name = body.get("name", "Imported Portfolio")
        csv_content = body.get("csv_content") or body.get("csv_text") or ""
        description = body.get("description")
        as_of_raw = body.get("as_of")
        as_of = date.fromisoformat(as_of_raw) if as_of_raw else None
        owner_ref = body.get("owner_ref", "local-user")
    else:
        form = await request.form()
        name = str(form.get("name") or "Imported Portfolio")
        description = form.get("description")
        description = str(description) if description is not None else None
        as_of_raw = form.get("as_of")
        as_of = date.fromisoformat(str(as_of_raw)) if as_of_raw else None
        owner_ref = str(form.get("owner_ref") or "local-user")
        upload_file = form.get("file")
        if upload_file is not None and hasattr(upload_file, "read"):
            content_bytes = await upload_file.read()
            csv_content = content_bytes.decode("utf-8", errors="replace")
        else:
            csv_content = str(form.get("csv_text") or form.get("csv_content") or "")

    if not csv_content.strip():
        return PortfolioImportResult(
            errors=[RowValidationError(row=1, error="CSV content is empty")]
        )

    return portfolio_service.import_portfolio_csv(
        session,
        name=name,
        csv_content=csv_content,
        as_of=as_of,
        description=description,
        owner_ref=owner_ref,
    )


@router.get("/portfolios", response_model=list[PortfolioOut], tags=["portfolio"])
def list_portfolios(
    session: DatabaseSession,
    owner_ref: str = "local-user",
) -> list[PortfolioOut]:
    """List all portfolios owned by owner_ref."""
    return portfolio_service.list_portfolios(session, owner_ref=owner_ref)


@router.get(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioOut,
    tags=["portfolio"],
)
def get_portfolio(
    portfolio_id: UUID,
    session: DatabaseSession,
) -> PortfolioOut:
    """Retrieve portfolio details and current holdings snapshot."""
    return portfolio_service.get_portfolio(session, portfolio_id=portfolio_id)


@router.post(
    "/portfolios/{portfolio_id}/risk-runs",
    response_model=PortfolioRiskRunOut,
    tags=["portfolio"],
)
def run_portfolio_risk(
    portfolio_id: UUID,
    req: RiskRunRequest,
    session: DatabaseSession,
) -> PortfolioRiskRunOut:
    """Execute Ledoit-Wolf covariance shrinkage and risk decomposition."""
    return portfolio_service.run_portfolio_risk(session, portfolio_id=portfolio_id, req=req)


@router.get(
    "/portfolios/{portfolio_id}/risk/latest",
    response_model=PortfolioRiskRunOut,
    tags=["portfolio"],
)
def get_latest_portfolio_risk(
    portfolio_id: UUID,
    session: DatabaseSession,
) -> PortfolioRiskRunOut:
    """Retrieve the latest risk run and result envelope for a portfolio."""
    return portfolio_service.get_latest_risk_run(session, portfolio_id=portfolio_id)


@router.get(
    "/portfolios/{portfolio_id}/risk-score/latest",
    response_model=PortfolioRiskScoreOut,
    tags=["portfolio"],
)
def get_latest_portfolio_risk_score(
    portfolio_id: UUID,
    session: DatabaseSession,
) -> PortfolioRiskScoreOut:
    """Return holding-risk and structural-risk synthesis with confidence."""
    return portfolio_service.get_latest_portfolio_risk_score(session, portfolio_id)


@router.post(
    "/portfolios/{portfolio_id}/diversification",
    response_model=DiversificationResponse,
    tags=["portfolio"],
)
def get_or_run_portfolio_diversification(
    portfolio_id: UUID,
    session: DatabaseSession,
) -> DiversificationResponse:
    """Retrieve or compute diversification analysis (ENB, cluster findings, suggestions)."""
    return portfolio_service.get_or_run_portfolio_diversification(
        session, portfolio_id=portfolio_id
    )


@router.post(
    "/portfolios/{portfolio_id}/shocks",
    response_model=ShockScenarioResponse,
    tags=["portfolio"],
)
def run_shock_simulation(
    portfolio_id: UUID,
    payload: ShockRequest,
    session: DatabaseSession,
) -> ShockScenarioResponse:
    """Simulate shock propagation across portfolio holdings (regression beta or MST decay)."""
    return portfolio_service.run_shock_simulation(
        session, portfolio_id=portfolio_id, payload=payload
    )


@router.get(
    "/portfolios/{portfolio_id}/shocks/{scenario_id}",
    response_model=ShockScenarioResponse,
    tags=["portfolio"],
)
def get_shock_scenario(
    portfolio_id: UUID,
    scenario_id: UUID,
    session: DatabaseSession,
) -> ShockScenarioResponse:
    """Retrieve a previously calculated shock scenario and holding impact results."""
    return portfolio_service.get_shock_scenario(
        session, portfolio_id=portfolio_id, scenario_id=scenario_id
    )


# ---------------------------------------------------------------------------
# Step 5: Multi-Dimensional Stock Risk Scores (D2, D3, D5)
# ---------------------------------------------------------------------------


@router.get("/stocks/scores/latest", tags=["stocks"])
def get_stock_scores_latest(
    session: DatabaseSession,
    industry: str | None = None,
    sort_by: str = Query(default="risk", pattern="^(risk|confidence|coverage|symbol)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Retrieve screener table of latest multi-dimensional stock risk scores."""
    return get_latest_stock_scores(
        session=session,
        industry=industry,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/stocks/{symbol}/risk/latest", tags=["stocks"])
def get_stock_risk_latest(
    symbol: str,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Retrieve full D3 Result Envelope for a specific stock with generic components array."""
    envelope = get_stock_risk_envelope(session=session, symbol=symbol)
    if envelope is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No risk score result available for symbol '{symbol}'",
        )
    return envelope


@router.get("/stocks/{symbol}/risk/history", tags=["stocks"])
def get_stock_risk_history_endpoint(
    symbol: str,
    session: DatabaseSession,
    limit: int = Query(default=30, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Retrieve historical time-series risk score trajectory for a stock."""
    return get_stock_risk_history(session=session, symbol=symbol, limit=limit)


@router.get("/stocks/{symbol}/fundamentals", tags=["stocks", "fundamentals"])
def get_stock_fundamentals_endpoint(
    symbol: str,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Retrieve quarterly financial periods, derived TTM ratios, and peer percentiles."""
    data = get_stock_fundamentals(session=session, symbol=symbol)
    if data is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Security with symbol '{symbol}' not found",
        )
    return data


# ---------------------------------------------------------------------------
# Step 8: Governance Signals (shareholding pattern, insider trades)
# ---------------------------------------------------------------------------


@router.get("/stocks/{symbol}/governance", tags=["stocks", "governance"])
def get_stock_governance(
    symbol: str,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Retrieve point-in-time governance signals for a stock.

    Returns SEBI Reg 31 shareholding pattern (pledge trend, promoter/FII/DII table)
    and SEBI PIT Reg 7(2) / SAST insider trade disclosures within a rolling window.

    All data is descriptive. No look-ahead. published_at is the actual SEBI
    filing date from the exchange record — never estimated.

    Limitations:
    - Shareholding data from SEBI Reg 31 quarterly filings (21-day filing lag).
    - Insider data from SEBI PIT Reg 7(2) / SAST Reg 29/31 CSV import.
    - Source: CSV import adapter; live exchange API requires ToS agreement.
    - MST/correlation is never presented as causal.
    """
    from backend.app.core.model_config import load_model_config
    from backend.app.db.models import SecurityAlias
    from backend.app.governance.config import GovernanceAnalysisConfig
    from backend.app.governance.service import get_governance_signals

    # Load config from DB (falls back to class defaults if not yet migrated)
    try:
        cfg_envelope = load_model_config(session, "governance_analysis", approved_only=False)
        gov_config = GovernanceAnalysisConfig(**cfg_envelope.configuration)
    except Exception:
        gov_config = GovernanceAnalysisConfig()

    norm_symbol = symbol.strip().upper()

    # Fetch latest market cap for insider ratio computation
    market_cap_inr: float | None = None
    alias_row = session.scalars(
        select(SecurityAlias).where(SecurityAlias.symbol == norm_symbol)
    ).first()
    if alias_row is not None:
        latest_stat = session.scalar(
            select(SecurityMarketStat)
            .where(SecurityMarketStat.security_id == alias_row.security_id)
            .order_by(SecurityMarketStat.trade_date.desc())
            .limit(1)
        )
        if latest_stat is not None and latest_stat.market_cap is not None:
            market_cap_inr = float(latest_stat.market_cap)

    data = get_governance_signals(
        session=session,
        symbol=norm_symbol,
        config=gov_config,
        market_cap_inr=market_cap_inr,
    )
    if data is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Security with symbol '{symbol}' not found",
        )
    return data


# -----------------------------------------------------------------------------
# Macroeconomic Regime & Sector Sensitivity Endpoints (Step 9)
# -----------------------------------------------------------------------------


@router.get(
    "/macro/regime/latest",
    response_model=MarketRegimeOut,
    tags=["macro"],
    summary="Get latest point-in-time market regime",
)
def read_latest_market_regime(
    session: DatabaseSession,
    as_of: date | None = None,
) -> MarketRegimeOut:
    """Retrieve the latest point-in-time rule-based market regime state."""
    from backend.app.macro.service import get_latest_market_regime

    return get_latest_market_regime(session, as_of=as_of)


@router.get(
    "/macro/series",
    response_model=list[MacroSeriesDefinitionOut],
    tags=["macro"],
    summary="List all registered macroeconomic series",
)
def read_macro_series_list(
    session: DatabaseSession,
) -> list[MacroSeriesDefinitionOut]:
    """List all registered macroeconomic and market series definitions."""
    from backend.app.macro.service import list_macro_series

    return list_macro_series(session)


@router.get(
    "/macro/series/{key}",
    response_model=MacroSeriesDetailOut,
    tags=["macro"],
    summary="Get macroeconomic series observations",
)
def read_macro_series_detail(
    key: str,
    session: DatabaseSession,
    as_of: date | None = None,
    limit: int = Query(500, ge=1, le=2000),
) -> MacroSeriesDetailOut:
    """Retrieve detailed time series observations for a specific macro key."""
    from backend.app.macro.service import get_macro_series_detail

    detail = get_macro_series_detail(session, series_key=key.lower(), as_of=as_of, limit=limit)
    if not detail:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Macro series with key '{key}' not found",
        )
    return detail


@router.get(
    "/macro/sensitivities",
    response_model=list[SectorMacroSensitivityOut],
    tags=["macro"],
    summary="Get all sector macroeconomic sensitivities",
)
def read_all_macro_sensitivities(
    session: DatabaseSession,
    industry: str | None = None,
    series_key: str | None = None,
    as_of: date | None = None,
) -> list[SectorMacroSensitivityOut]:
    """Retrieve all latest sector sensitivities across all industries and macro series."""
    from backend.app.macro.service import get_all_sector_sensitivities

    return get_all_sector_sensitivities(
        session,
        industry=industry,
        series_key=series_key,
        as_of=as_of,
    )


@router.get(
    "/industries/{industry}/macro-sensitivity",
    response_model=list[SectorMacroSensitivityOut],
    tags=["macro"],
    summary="Get sector macroeconomic sensitivities",
)
def read_industry_macro_sensitivity(
    industry: str,
    session: DatabaseSession,
    as_of: date | None = None,
) -> list[SectorMacroSensitivityOut]:
    """Retrieve rolling OLS regression sensitivities for a sector across macro series."""
    from backend.app.macro.service import get_industry_macro_sensitivities

    return get_industry_macro_sensitivities(session, industry=industry, as_of=as_of)


@router.get(
    "/stocks/{symbol}/macro",
    response_model=StockMacroExposureOut,
    tags=["macro"],
    summary="Get stock macro exposure profile",
)
def read_stock_macro_profile(
    symbol: str,
    session: DatabaseSession,
    as_of: date | None = None,
) -> StockMacroExposureOut:
    """Retrieve full macro exposure profile for a specific stock."""
    from backend.app.macro.service import get_stock_macro_profile

    profile = get_stock_macro_profile(session, symbol=symbol.strip().upper(), as_of=as_of)
    if not profile:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Stock with symbol '{symbol}' not found",
        )
    return profile


# --- Step 10: Corporate Announcements & Explainable Events ---


@router.get(
    "/stocks/{symbol}/events",
    response_model=StockEventsResponse,
    tags=["events"],
    summary="Get corporate announcements and explainable events timeline for a stock",
)
def read_stock_events(
    symbol: str,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> StockEventsResponse:
    """Retrieve chronologically ordered corporate announcements and NLP sentiment signals."""
    from backend.app.events.service import get_stock_events

    res = get_stock_events(session, symbol=symbol, limit=limit)
    if not res:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Stock with symbol '{symbol}' not found or has no registered entity",
        )
    return res


@router.get(
    "/events/recent",
    response_model=RecentEventsResponse,
    tags=["events"],
    summary="Get recent corporate announcements feed across stocks",
)
def read_recent_events(
    session: DatabaseSession,
    event_type: Annotated[str | None, Query(description="Filter by event type")] = None,
    min_importance: Annotated[
        float | None, Query(ge=1.0, le=10.0, description="Minimum importance score")
    ] = None,
    since_date: Annotated[
        date | None, Query(description="Filter events effective on or after date")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RecentEventsResponse:
    """Retrieve recent corporate announcements and explainable events feed with optional filters."""
    from backend.app.events.service import get_recent_events

    return get_recent_events(
        session,
        event_type=event_type,
        min_importance=min_importance,
        since_date=since_date,
        limit=limit,
    )


# --- Step 11: Timestamped News & Policy Rules ---


@router.get(
    "/stocks/{symbol}/news",
    response_model=StockNewsResponse,
    tags=["policy"],
    summary="Get news and policy events dossier for a stock",
)
def read_stock_news(
    symbol: str,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StockNewsResponse:
    """Retrieve news announcements and matched policy headwinds/tailwinds for a stock's industry."""
    from backend.app.policy.service import get_stock_news

    return get_stock_news(session, symbol=symbol, limit=limit)


@router.get(
    "/policy/rules",
    response_model=list[PolicyRuleOut],
    tags=["policy"],
    summary="List policy-to-sector rules",
)
def read_policy_rules(
    session: DatabaseSession,
    active_only: Annotated[bool, Query(description="Filter active rules only")] = False,
    category: Annotated[str | None, Query(description="Filter by match category")] = None,
) -> list[PolicyRuleOut]:
    """Retrieve editable policy rules with version, reviewer, and economic rationale."""
    from backend.app.policy.service import list_policy_rules

    return list_policy_rules(session, active_only=active_only, category=category)


@router.get(
    "/policy/events/recent",
    response_model=RecentPolicyEventsResponse,
    tags=["policy"],
    summary="Get recent policy events across industries",
)
def read_recent_policy_events(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    industry: Annotated[str | None, Query(description="Filter by affected industry")] = None,
) -> RecentPolicyEventsResponse:
    """Retrieve recent policy and regulatory events with economic evidence and rationales."""
    from backend.app.policy.service import list_recent_policy_events

    return list_recent_policy_events(session, limit=limit, industry=industry)


@router.put(
    "/policy/rules/{key}",
    response_model=PolicyRuleOut,
    tags=["policy"],
    summary="Update or create a policy rule version (requires reviewer and rationale)",
)
def update_policy_rule_endpoint(
    key: str,
    update: PolicyRuleUpdate,
    session: DatabaseSession,
) -> PolicyRuleOut:
    """Create a new version of a policy rule enforcing reviewer and written
    economic rationale (D1).
    """
    from backend.app.policy.service import update_policy_rule

    return update_policy_rule(session, key=key, update=update)
