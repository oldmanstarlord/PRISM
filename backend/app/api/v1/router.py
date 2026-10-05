from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.correlation_mst.service import latest_completed_mst_query
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
from backend.app.fundamentals.service import get_stock_fundamentals
from backend.app.mst_diagnostics.config import load_mst_diagnostics_config
from backend.app.mst_diagnostics.stability import calculate_stability_grade
from backend.app.portfolio import service as portfolio_service
from backend.app.portfolio.schemas import (
    DiversificationResponse,
    PortfolioCreate,
    PortfolioImportResult,
    PortfolioOut,
    PortfolioRiskRunOut,
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

router = APIRouter()
DatabaseSession = Annotated[Session, Depends(get_session)]


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
            "The MST retains only N-1 relationships and omits many valid correlations.",
            "The topology can change when the lookback window or eligible universe changes.",
            "Edges are a sparse subset of all pairwise relationships.",
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
