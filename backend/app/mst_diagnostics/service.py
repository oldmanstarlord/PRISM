"""Service layer for MST diagnostics, stability tracking, clustering, and variant runs."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.calculator import calculate_mst
from backend.app.correlation_mst.inputs import (
    FORMULA_VERSION,
    load_inputs,
)
from backend.app.correlation_mst.service import (
    PersistedMst,
    _canonical_hash,
    mst_configuration,
    mst_input_fingerprint,
)
from backend.app.db.models import (
    MstCluster,
    MstEdge,
    MstNodeMetric,
    MstRun,
    MstStability,
    Universe,
)
from backend.app.db.models import (
    MstNode as StoredMstNode,
)
from backend.app.mst_diagnostics.clustering import (
    EdgeData,
    compute_mst_clusters_and_metrics,
)
from backend.app.mst_diagnostics.config import (
    MstDiagnosticsConfig,
    load_mst_diagnostics_config,
)
from backend.app.mst_diagnostics.residual import build_residual_inputs
from backend.app.mst_diagnostics.stability import (
    calculate_tree_stability,
)


@dataclass(frozen=True, slots=True)
class DiagnosticsExecutionResult:
    run_id: UUID
    variant: str
    stability_calculated: bool
    clusters_count: int
    node_metrics_count: int
    edge_persistence: float | None
    stability_grade: str | None


def persist_residual_mst(
    session: Session,
    *,
    window_end: date,
    lookback_start: date,
    data_cutoff: datetime,
    computed_at: datetime | None = None,
    benchmark_id: str = "NIFTY_200",
    benchmark_name: str | None = None,
) -> PersistedMst:
    """Build residual inputs and persist residual MST run via unchanged calculator."""
    raw_inputs = load_inputs(session, window_end, lookback_start, data_cutoff)
    residual_inputs, residual_meta = build_residual_inputs(
        raw_inputs,
        session=session,
        benchmark_id=benchmark_id,
        benchmark_name=benchmark_name,
    )

    configuration = mst_configuration()
    configuration["variant"] = "residual"
    configuration["residual_metadata"] = residual_meta
    configuration_hash = _canonical_hash(configuration)
    fingerprint = mst_input_fingerprint(residual_inputs)

    existing = session.scalar(
        select(MstRun).where(
            MstRun.window_end == window_end,
            MstRun.implementation_version == FORMULA_VERSION,
            MstRun.configuration_hash == configuration_hash,
            MstRun.input_fingerprint == fingerprint,
            MstRun.status == "completed",
        )
    )
    if existing is not None:
        return PersistedMst(
            existing.id,
            False,
            existing.included_symbol_count,
            existing.edge_count,
            existing.requested_symbol_count - existing.included_symbol_count,
        )

    universe_id = session.scalar(select(Universe.id).where(Universe.name == "NIFTY 200"))
    if universe_id is None:
        raise ValueError("NIFTY 200 universe is not seeded")

    calculation_time = computed_at or datetime.now(UTC)
    calculation = calculate_mst(residual_inputs, computed_at=calculation_time)

    exclusions = {
        "items": [
            {
                "security_id": str(item.security_id),
                "symbol": item.symbol,
                "reason": item.reason,
                "details": item.details,
            }
            for item in calculation.exclusions
        ]
    }

    run = MstRun(
        universe_id=universe_id,
        window_start=calculation.window_start,
        window_end=calculation.window_end,
        data_cutoff=data_cutoff,
        requested_symbol_count=len(residual_inputs.security_ids),
        included_symbol_count=len(calculation.nodes),
        edge_count=len(calculation.edges),
        is_connected=calculation.is_connected,
        is_acyclic=calculation.is_acyclic,
        exclusions=exclusions,
        configuration=configuration,
        configuration_hash=configuration_hash,
        input_fingerprint=fingerprint,
        status="completed",
        implementation_version=FORMULA_VERSION,
        computed_at=calculation_time,
    )
    session.add(run)
    session.flush()

    session.add_all(
        [
            StoredMstNode(
                mst_run_id=run.id,
                security_id=node.security_id,
                symbol=node.symbol,
                industry=node.industry,
                observations_used=node.observations_used,
                membership_source=node.membership_source,
            )
            for node in calculation.nodes
        ]
    )
    session.add_all(
        [
            MstEdge(
                mst_run_id=run.id,
                security_a_id=edge.security_a_id,
                security_b_id=edge.security_b_id,
                symbol_a=edge.symbol_a,
                symbol_b=edge.symbol_b,
                correlation=Decimal(str(edge.correlation)),
                distance=Decimal(str(edge.distance)),
                paired_observations=edge.paired_observations,
                edge_rank=edge.edge_rank,
            )
            for edge in calculation.edges
        ]
    )
    session.commit()

    return PersistedMst(
        run.id, True, run.included_symbol_count, run.edge_count, len(calculation.exclusions)
    )


def compute_and_persist_diagnostics(
    session: Session,
    run_id: UUID,
    config: MstDiagnosticsConfig | None = None,
) -> DiagnosticsExecutionResult:
    """Compute and persist stability, clusters, and node metrics for an MST run."""
    effective_config = config or load_mst_diagnostics_config(session)
    run = session.get(MstRun, run_id)
    if run is None:
        raise ValueError(f"MstRun {run_id} does not exist")

    variant = str(run.configuration.get("variant", "raw") if run.configuration else "raw")

    # 1. Fetch current edges and nodes
    edges = session.scalars(
        select(MstEdge).where(MstEdge.mst_run_id == run.id).order_by(MstEdge.edge_rank)
    ).all()
    nodes = session.scalars(
        select(StoredMstNode)
        .where(StoredMstNode.mst_run_id == run.id)
        .order_by(StoredMstNode.symbol)
    ).all()

    edge_data_list = [
        EdgeData(
            symbol_a=str(e.symbol_a or ""),
            symbol_b=str(e.symbol_b or ""),
            distance=float(e.distance),
            correlation=float(e.correlation) if e.correlation is not None else 0.0,
            edge_rank=e.edge_rank,
        )
        for e in edges
    ]
    symbols_with_ids = {n.symbol: n.security_id for n in nodes}

    # 2. Compute Clusters and Node Metrics
    clustering_res = compute_mst_clusters_and_metrics(
        symbols_with_ids=symbols_with_ids,
        edges=edge_data_list,
        k_cut=effective_config.cluster_k_cut,
        cluster_rule_version=effective_config.cluster_rule_version,
    )

    # Persist clusters (idempotent / clean prior for same run + rule version)
    existing_clusters = session.scalars(
        select(MstCluster).where(
            MstCluster.run_id == run.id,
            MstCluster.cluster_rule_version == effective_config.cluster_rule_version,
        )
    ).all()
    if not existing_clusters:
        session.add_all(
            [
                MstCluster(
                    id=uuid4(),
                    run_id=run.id,
                    security_id=asgn.security_id,
                    symbol=asgn.symbol,
                    cluster_id=asgn.cluster_id,
                    cluster_rule_version=asgn.cluster_rule_version,
                    cluster_size=asgn.cluster_size,
                )
                for asgn in clustering_res.assignments
            ]
        )

    # Persist node metrics
    existing_metrics = session.scalars(
        select(MstNodeMetric).where(MstNodeMetric.run_id == run.id)
    ).all()
    if not existing_metrics:
        session.add_all(
            [
                MstNodeMetric(
                    id=uuid4(),
                    run_id=run.id,
                    security_id=nm.security_id,
                    symbol=nm.symbol,
                    degree=nm.degree,
                    weighted_centrality=Decimal(str(nm.weighted_centrality)),
                    hub_rank=nm.hub_rank,
                )
                for nm in clustering_res.node_metrics
            ]
        )

    # 3. Stability: Find prior run of the same variant
    stability_calculated = False
    edge_persistence: float | None = None
    stability_grade: str | None = None

    prior_candidates = session.scalars(
        select(MstRun)
        .where(
            MstRun.status == "completed",
            MstRun.window_end < run.window_end,
        )
        .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
    ).all()

    prior_run = next(
        (p for p in prior_candidates if (p.configuration or {}).get("variant", "raw") == variant),
        None,
    )

    if prior_run is not None:
        prior_edges = session.scalars(
            select(MstEdge).where(MstEdge.mst_run_id == prior_run.id)
        ).all()
        prior_nodes = session.scalars(
            select(StoredMstNode).where(StoredMstNode.mst_run_id == prior_run.id)
        ).all()

        current_edge_pairs = [(str(e.symbol_a or ""), str(e.symbol_b or "")) for e in edges]
        prior_edge_pairs = [(str(e.symbol_a or ""), str(e.symbol_b or "")) for e in prior_edges]

        current_node_symbols = [n.symbol for n in nodes]
        prior_node_symbols = [n.symbol for n in prior_nodes]

        stability_res = calculate_tree_stability(
            run_id=run.id,
            prior_run_id=prior_run.id,
            current_edges=current_edge_pairs,
            prior_edges=prior_edge_pairs,
            current_nodes=current_node_symbols,
            prior_nodes=prior_node_symbols,
            current_window_end=run.window_end,
            prior_window_end=prior_run.window_end,
            config=effective_config,
        )

        existing_stability = session.scalar(
            select(MstStability).where(
                MstStability.run_id == run.id,
                MstStability.prior_run_id == prior_run.id,
            )
        )
        if existing_stability is None:
            session.add(
                MstStability(
                    id=uuid4(),
                    run_id=run.id,
                    prior_run_id=prior_run.id,
                    edge_persistence=Decimal(str(stability_res.edge_persistence)),
                    node_overlap=Decimal(str(stability_res.node_overlap)),
                    window_gap_days=stability_res.window_gap_days,
                    details=stability_res.details,
                )
            )

        stability_calculated = True
        edge_persistence = stability_res.edge_persistence
        stability_grade = stability_res.grade

    session.commit()

    return DiagnosticsExecutionResult(
        run_id=run.id,
        variant=variant,
        stability_calculated=stability_calculated,
        clusters_count=len(clustering_res.clusters),
        node_metrics_count=len(clustering_res.node_metrics),
        edge_persistence=edge_persistence,
        stability_grade=stability_grade,
    )


def get_latest_mst_run_for_variant(
    session: Session,
    variant: str = "raw",
) -> MstRun | None:
    """Retrieve the latest completed MstRun matching the requested variant."""
    runs = session.scalars(
        select(MstRun)
        .where(MstRun.status == "completed")
        .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
    ).all()
    for r in runs:
        r_var = (r.configuration or {}).get("variant", "raw")
        if r_var == variant:
            return r
    return None
