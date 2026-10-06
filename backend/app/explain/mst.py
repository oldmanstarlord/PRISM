"""Evidence-bound edge, pair, and node explainers for persisted Layer 2 outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.inputs import load_inputs
from backend.app.db.models import (
    EventItem,
    MstCluster,
    MstEdge,
    MstNode,
    MstNodeMetric,
    MstRun,
    NewsItem,
    NewsSecurityLink,
    PortfolioRiskContribution,
    PortfolioRiskRun,
    SectorMacroSensitivity,
)
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import evidence_bound_sentences
from backend.app.explain.mst_math import (
    PairStatistics,
    downsample,
    pair_statistics,
    persistence_summary,
    reconstruct_accepted_steps,
    tree_path,
)
from backend.app.explain.registry import registry
from backend.app.explain.schemas import (
    ExplanationConfidence,
    ExplanationDataAge,
    ExplanationPayload,
    ExplanationSection,
    ExplanationSentence,
    ExplanationSubject,
)
from backend.app.explain.templates import build_sentence
from backend.app.mst_diagnostics.residual import build_residual_inputs
from backend.app.mst_diagnostics.stability import calculate_stability_grade
from backend.app.sector_divergence.inputs import load_latest_adjusted_closes


@dataclass(frozen=True)
class MstEdgeSubject:
    run_id: UUID
    a: str
    b: str
    portfolio_id: UUID | None = None

    @property
    def key(self) -> str:
        left, right = sorted((self.a.upper(), self.b.upper()))
        suffix = f":{self.portfolio_id}" if self.portfolio_id else ""
        return f"{self.run_id}:{left}:{right}{suffix}"


@dataclass(frozen=True)
class MstPairSubject:
    a: str
    b: str
    portfolio_id: UUID | None = None

    @property
    def key(self) -> str:
        left, right = sorted((self.a.upper(), self.b.upper()))
        suffix = f":{self.portfolio_id}" if self.portfolio_id else ""
        return f"{left}:{right}{suffix}"


@dataclass(frozen=True)
class MstNodeSubject:
    symbol: str
    portfolio_id: UUID | None = None

    @property
    def key(self) -> str:
        suffix = f":{self.portfolio_id}" if self.portfolio_id else ""
        return f"{self.symbol.upper()}{suffix}"


def _ev(
    evidence_id: str,
    label: str,
    value: str | int | float | bool | None,
    run: MstRun,
    *,
    source_table: str,
    source_ref: str,
    unit: str | None = None,
    window: str | None = None,
    kind: Literal["statistic", "rule", "event", "config"] = "statistic",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind=kind,
        label=label,
        value=value,
        unit=unit,
        window=window,
        source_table=source_table,
        source_ref=source_ref,
        as_of=run.window_end,
        data_age_days=max(0, (run.computed_at.date() - run.window_end).days),
    )


def _latest_raw_run(session: Session, as_of: date | None = None) -> MstRun:
    query = select(MstRun).where(MstRun.status == "completed")
    if as_of is not None:
        query = query.where(MstRun.window_end <= as_of)
    runs = session.scalars(query.order_by(desc(MstRun.window_end), desc(MstRun.computed_at))).all()
    run = next(
        (row for row in runs if (row.configuration or {}).get("variant", "raw") == "raw"), None
    )
    if run is None:
        raise LookupError("no completed raw MST run is available")
    return run


def _run_context(session: Session, run: MstRun) -> tuple[dict[str, MstNode], list[MstEdge]]:
    nodes = {
        node.symbol.upper(): node
        for node in session.scalars(
            select(MstNode).where(MstNode.mst_run_id == run.id).order_by(MstNode.symbol)
        ).all()
    }
    edges = session.scalars(
        select(MstEdge).where(MstEdge.mst_run_id == run.id).order_by(MstEdge.edge_rank)
    ).all()
    return nodes, list(edges)


def _price_panel(session: Session, run: MstRun, nodes: dict[str, MstNode]) -> pd.DataFrame:
    if run.data_cutoff is None:
        raise LookupError("MST run has no point-in-time data cutoff")
    observations = load_latest_adjusted_closes(
        session,
        [node.security_id for node in nodes.values()],
        run.window_start - timedelta(days=45),
        run.window_end,
        run.data_cutoff,
    )
    symbols = {node.security_id: symbol for symbol, node in nodes.items()}
    dates = sorted({item.trade_date for item in observations})[-121:]
    panel = pd.DataFrame(
        index=pd.Index(dates, name="trade_date"), columns=sorted(nodes), dtype=float
    )
    selected_dates = set(dates)
    for item in observations:
        if item.trade_date in selected_dates:
            panel.at[item.trade_date, symbols[item.security_id]] = float(item.adjusted_close)
    return panel


def _edge_key(a: str, b: str) -> tuple[str, str]:
    left, right = sorted((a.upper(), b.upper()))
    return left, right


def _num(item: Evidence) -> float:
    if isinstance(item.value, bool) or not isinstance(item.value, (int, float)):
        raise ValueError(f"evidence {item.evidence_id} is not numeric")
    return float(item.value)


def _edge_for(edges: list[MstEdge], a: str, b: str) -> MstEdge | None:
    target = _edge_key(a, b)
    return next(
        (edge for edge in edges if _edge_key(str(edge.symbol_a), str(edge.symbol_b)) == target),
        None,
    )


def _pair_rank(panel: pd.DataFrame, a: str, b: str) -> tuple[int, int]:
    returns = np.log(panel.astype(float)).diff().tail(120)

    def rank(source: str, target: str) -> int:
        values: list[tuple[float, str]] = []
        for other in panel.columns:
            if other == source:
                continue
            paired = returns[[source, other]].dropna()
            if len(paired) >= 2:
                values.append((float(paired[source].corr(paired[other])), str(other)))
        values.sort(key=lambda item: (-item[0], item[1]))
        return next(index for index, (_, symbol) in enumerate(values, 1) if symbol == target)

    return rank(a, b), rank(b, a)


def _chart_json(
    panel: pd.DataFrame, a: str, b: str, maximum: int, rolling_window: int
) -> tuple[str, str]:
    returns = np.log(panel[[a, b]].astype(float)).diff().tail(120)
    paired = returns.dropna()
    scatter = downsample(
        [
            {"date": str(index), "x": float(row[a]), "y": float(row[b])}
            for index, row in paired.iterrows()
        ],
        maximum,
    )
    minimum_periods = min(20, rolling_window)
    rolling = (
        returns[a].rolling(rolling_window, min_periods=minimum_periods).corr(returns[b]).dropna()
    )
    rolling_points = downsample(
        [{"date": str(index), "value": float(value)} for index, value in rolling.items()],
        maximum,
    )
    return json.dumps(rolling_points, separators=(",", ":")), json.dumps(
        scatter, separators=(",", ":")
    )


def _history(
    session: Session,
    run: MstRun,
    a: str,
    b: str,
    count: int,
) -> tuple[int, int, float, float | None, float | None, float | None]:
    candidates = session.scalars(
        select(MstRun)
        .where(MstRun.status == "completed", MstRun.window_end <= run.window_end)
        .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
    ).all()
    runs = [row for row in candidates if (row.configuration or {}).get("variant", "raw") == "raw"][
        :count
    ]
    present: list[bool] = []
    correlations: list[float] = []
    for item in reversed(runs):
        nodes, edges = _run_context(session, item)
        if a not in nodes or b not in nodes:
            continue
        present.append(_edge_for(edges, a, b) is not None)
        try:
            correlations.append(
                pair_statistics(
                    _price_panel(session, item, nodes), a, b, item.window_end
                ).correlation
            )
        except ValueError:
            present.pop()
    summary = persistence_summary(present, correlations)
    return (
        summary.present_windows,
        summary.total_windows,
        summary.share,
        summary.minimum,
        summary.median,
        summary.maximum,
    )


def _common_evidence(
    session: Session,
    run: MstRun,
    a: str,
    b: str,
    config: dict[str, Any],
) -> tuple[list[Evidence], PairStatistics, dict[str, MstNode], list[MstEdge]]:
    nodes, edges = _run_context(session, run)
    if a not in nodes or b not in nodes:
        raise LookupError(f"both {a} and {b} must be nodes in MST run {run.id}")
    panel = _price_panel(session, run, nodes)
    stats = pair_statistics(panel, a, b, run.window_end)
    edge = _edge_for(edges, a, b)
    rank_ab, rank_ba = _pair_rank(panel, a, b)
    rolling_json, scatter_json = _chart_json(
        panel,
        a,
        b,
        int(config["max_chart_points"]),
        int(config["rolling_correlation_days"]),
    )
    evidence = [
        _ev(
            "run_id", "Run ID", str(run.id), run, source_table="mst_run", source_ref=f"{run.id}:id"
        ),
        _ev(
            "run_start",
            "Run window start",
            str(run.window_start),
            run,
            source_table="mst_run",
            source_ref=f"{run.id}:window_start",
        ),
        _ev(
            "run_computed_at",
            "Run computation time",
            run.computed_at.isoformat(),
            run,
            source_table="mst_run",
            source_ref=f"{run.id}:computed_at",
        ),
        _ev(
            "method_version",
            "Layer 2 method version",
            run.implementation_version,
            run,
            source_table="mst_run",
            source_ref=f"{run.id}:implementation_version",
            kind="config",
        ),
        _ev(
            "run_window",
            "Run window",
            f"{run.window_start}/{run.window_end}",
            run,
            source_table="mst_run",
            source_ref=f"{run.id}:window",
            window="120 daily log returns",
        ),
        _ev(
            "correlation",
            "Direct correlation",
            stats.correlation,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:{b}:recomputed",
            unit="correlation",
            window="120 daily log returns",
        ),
        _ev(
            "distance",
            "Mantegna distance",
            stats.distance,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:{b}:distance",
            unit="distance",
            window="120 daily log returns",
        ),
        _ev(
            "observations",
            "Paired observations",
            stats.observations,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:{b}:paired",
            unit="returns",
        ),
        _ev(
            "beta",
            "Beta of B on A",
            stats.beta_b_on_a,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{b}_on_{a}:beta",
            unit="beta",
        ),
        _ev(
            "r_squared",
            "R-squared",
            stats.r_squared,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:{b}:r_squared",
            unit="ratio",
        ),
        _ev(
            "rank_ab",
            f"{b} neighbour rank for {a}",
            rank_ab,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:correlation_rank",
        ),
        _ev(
            "rank_ba",
            f"{a} neighbour rank for {b}",
            rank_ba,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{b}:correlation_rank",
        ),
        _ev(
            "rolling_chart",
            "Rolling correlation chart",
            rolling_json,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:{b}:rolling_60",
            window="60 returns",
        ),
        _ev(
            "scatter_chart",
            "Returns scatter chart",
            scatter_json,
            run,
            source_table="price_daily_adjusted",
            source_ref=f"{run.id}:{a}:{b}:scatter",
            window="120 returns",
        ),
    ]
    if edge is not None:
        if edge.correlation is None or abs(float(edge.distance) - stats.distance) > 1e-8:
            raise ValueError("recomputed pair distance does not match the persisted edge")
        contexts = reconstruct_accepted_steps(
            sorted(nodes),
            [
                (str(item.symbol_a), str(item.symbol_b), float(item.distance), item.edge_rank)
                for item in edges
            ],
        )
        context = next(item for item in contexts if item.step == edge.edge_rank)
        evidence.extend(
            [
                _ev(
                    "edge_step",
                    "Kruskal acceptance step",
                    edge.edge_rank,
                    run,
                    source_table="mst_edge",
                    source_ref=f"{edge.id}:edge_rank",
                ),
                _ev(
                    "edge_count",
                    "Tree edge count",
                    run.edge_count,
                    run,
                    source_table="mst_run",
                    source_ref=f"{run.id}:edge_count",
                ),
                _ev(
                    "left_size",
                    "First joined group size",
                    context.left_size,
                    run,
                    source_table="mst_edge",
                    source_ref=f"{run.id}:reconstructed_group_size",
                ),
                _ev(
                    "right_size",
                    "Second joined group size",
                    context.right_size,
                    run,
                    source_table="mst_edge",
                    source_ref=f"{run.id}:reconstructed_group_size",
                ),
            ]
        )
    clusters = session.scalars(
        select(MstCluster).where(MstCluster.run_id == run.id, MstCluster.symbol.in_([a, b]))
    ).all()
    by_symbol = {item.symbol: item for item in clusters}
    if a in by_symbol and b in by_symbol:
        evidence.extend(
            [
                _ev(
                    "same_industry",
                    "Same industry",
                    nodes[a].industry == nodes[b].industry,
                    run,
                    source_table="mst_node",
                    source_ref=f"{nodes[a].id}:{nodes[b].id}:industry",
                ),
                _ev(
                    "same_cluster",
                    "Same cluster",
                    by_symbol[a].cluster_id == by_symbol[b].cluster_id,
                    run,
                    source_table="mst_cluster",
                    source_ref=f"{by_symbol[a].id}:{by_symbol[b].id}:cluster",
                ),
                _ev(
                    "cluster_rule",
                    "Cluster rule version",
                    by_symbol[a].cluster_rule_version,
                    run,
                    source_table="mst_cluster",
                    source_ref=f"{by_symbol[a].id}:cluster_rule_version",
                    kind="rule",
                ),
            ]
        )
    present, total, share, minimum, med, maximum = _history(
        session, run, a, b, int(config["history_windows_count"])
    )
    evidence.extend(
        [
            _ev(
                "present_windows",
                "Windows containing edge",
                present,
                run,
                source_table="mst_edge",
                source_ref=f"{a}:{b}:history",
            ),
            _ev(
                "total_windows",
                "Available history windows",
                total,
                run,
                source_table="mst_run",
                source_ref=f"{a}:{b}:history",
                window=f"last {config['history_windows_count']} configured windows",
            ),
            _ev(
                "persistence",
                "Pair edge persistence",
                share,
                run,
                source_table="mst_edge",
                source_ref=f"{a}:{b}:history",
                unit="ratio",
            ),
            _ev(
                "minimum_correlation",
                "Minimum window correlation",
                minimum,
                run,
                source_table="price_daily_adjusted",
                source_ref=f"{a}:{b}:history",
            ),
            _ev(
                "median_correlation",
                "Median window correlation",
                med,
                run,
                source_table="price_daily_adjusted",
                source_ref=f"{a}:{b}:history",
            ),
            _ev(
                "maximum_correlation",
                "Maximum window correlation",
                maximum,
                run,
                source_table="price_daily_adjusted",
                source_ref=f"{a}:{b}:history",
            ),
        ]
    )
    return evidence, stats, nodes, edges


def _add_optional_pair_evidence(
    session: Session,
    run: MstRun,
    a: str,
    b: str,
    nodes: dict[str, MstNode],
    evidence: list[Evidence],
    portfolio_id: UUID | None,
    config: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    try:
        if run.data_cutoff is None:
            raise ValueError("missing cutoff")
        raw = load_inputs(
            session, run.window_end, run.window_start - timedelta(days=45), run.data_cutoff
        )
        residual, _ = build_residual_inputs(raw, session=session)
        residual_stats = pair_statistics(residual.adjusted_closes, a, b, run.window_end)
        residual_runs = session.scalars(
            select(MstRun).where(MstRun.status == "completed", MstRun.window_end == run.window_end)
        ).all()
        residual_run = next(
            (
                item
                for item in residual_runs
                if (item.configuration or {}).get("variant") == "residual"
            ),
            None,
        )
        residual_edge = False
        if residual_run is not None:
            residual_edges = session.scalars(
                select(MstEdge).where(MstEdge.mst_run_id == residual_run.id)
            ).all()
            residual_edge = _edge_for(list(residual_edges), a, b) is not None
        evidence.extend(
            [
                _ev(
                    "residual_correlation",
                    "Residual correlation",
                    residual_stats.correlation,
                    run,
                    source_table="price_daily_adjusted",
                    source_ref=f"{run.id}:{a}:{b}:market_residual",
                ),
                _ev(
                    "residual_edge",
                    "Appears in residual tree",
                    residual_edge,
                    run,
                    source_table="mst_edge",
                    source_ref=f"{residual_run.id if residual_run else 'missing'}:{a}:{b}",
                ),
            ]
        )
    except (LookupError, ValueError, KeyError):
        missing.append(
            "Residual correlation was omitted: matching benchmark evidence was unavailable."
        )

    sensitivities = session.scalars(
        select(SectorMacroSensitivity)
        .where(
            SectorMacroSensitivity.industry.in_([nodes[a].industry, nodes[b].industry]),
            SectorMacroSensitivity.window_end <= run.window_end,
            SectorMacroSensitivity.is_significant.is_(True),
        )
        .order_by(desc(SectorMacroSensitivity.window_end))
    ).all()
    vectors: dict[str, dict[str, float]] = {nodes[a].industry: {}, nodes[b].industry: {}}
    refs: list[str] = []
    for item in sensitivities:
        if item.series_key not in vectors[item.industry]:
            vectors[item.industry][item.series_key] = item.beta
            refs.append(str(item.id))
    shared = sorted(set(vectors[nodes[a].industry]) & set(vectors[nodes[b].industry]))
    if shared:
        left = np.array([vectors[nodes[a].industry][key] for key in shared])
        right = np.array([vectors[nodes[b].industry][key] for key in shared])
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        similarity = float(np.dot(left, right) / denominator) if denominator else 0.0
        top = max(
            shared,
            key=lambda key: abs(vectors[nodes[a].industry][key] * vectors[nodes[b].industry][key]),
        )
        evidence.extend(
            [
                _ev(
                    "macro_similarity",
                    "Macro sensitivity similarity",
                    similarity,
                    run,
                    source_table="sector_macro_sensitivity",
                    source_ref=":".join(refs),
                    unit="cosine similarity",
                ),
                _ev(
                    "macro_driver",
                    "Top shared significant macro driver",
                    top,
                    run,
                    source_table="sector_macro_sensitivity",
                    source_ref=":".join(refs),
                ),
            ]
        )
    else:
        missing.append(
            "Macro similarity was omitted: no shared significant sensitivity was stored."
        )

    all_metrics = session.scalars(select(MstNodeMetric).where(MstNodeMetric.run_id == run.id)).all()
    metrics_by_symbol = {metric.symbol.upper(): metric for metric in all_metrics}
    clusters = session.scalars(select(MstCluster).where(MstCluster.run_id == run.id)).all()
    clusters_by_symbol = {cluster.symbol.upper(): cluster for cluster in clusters}
    centralities = [float(metric.weighted_centrality) for metric in all_metrics]
    if a in metrics_by_symbol and b in metrics_by_symbol and centralities:
        for symbol in (a, b):
            metric = metrics_by_symbol[symbol]
            centrality = float(metric.weighted_centrality)
            percentile = (
                100.0 * sum(value <= centrality for value in centralities) / len(centralities)
            )
            cluster = clusters_by_symbol.get(symbol)
            evidence.extend(
                [
                    _ev(
                        f"degree_{symbol}",
                        f"Degree {symbol}",
                        metric.degree,
                        run,
                        source_table="mst_node_metric",
                        source_ref=f"{metric.id}:degree",
                    ),
                    _ev(
                        f"centrality_{symbol}",
                        f"Centrality percentile {symbol}",
                        percentile,
                        run,
                        source_table="mst_node_metric",
                        source_ref=f"{metric.id}:weighted_centrality",
                        unit="percentile",
                    ),
                    _ev(
                        f"cluster_size_{symbol}",
                        f"Cluster size {symbol}",
                        cluster.cluster_size if cluster else None,
                        run,
                        source_table="mst_cluster",
                        source_ref=f"{cluster.id if cluster else 'missing'}:cluster_size",
                        unit="stocks",
                    ),
                ]
            )
    else:
        missing.append("Endpoint node metrics were omitted: diagnostics were unavailable.")

    event_lookback = int(config["event_lookback_days"])
    cutoff = run.window_end - timedelta(days=event_lookback)
    event_rows = session.scalars(
        select(EventItem).where(
            EventItem.security_id.in_([nodes[a].security_id, nodes[b].security_id]),
            EventItem.effective_trading_date.between(cutoff, run.window_end),
        )
    ).all()
    grouped: dict[tuple[date, str], set[UUID]] = {}
    for event_item in event_rows:
        grouped.setdefault((event_item.effective_trading_date, event_item.event_type), set()).add(
            event_item.security_id
        )
    event_count = sum(len(ids) == 2 for ids in grouped.values())
    news_rows = session.execute(
        select(NewsSecurityLink.news_item_id, NewsSecurityLink.security_id)
        .join(NewsItem, NewsItem.id == NewsSecurityLink.news_item_id)
        .where(
            NewsSecurityLink.security_id.in_([nodes[a].security_id, nodes[b].security_id]),
            func.date(NewsItem.published_at).between(cutoff, run.window_end),
        )
    ).all()
    news_groups: dict[UUID, set[UUID]] = {}
    for news_id, security_id in news_rows:
        news_groups.setdefault(news_id, set()).add(security_id)
    news_count = sum(len(ids) == 2 for ids in news_groups.values())
    cooccurring = event_count + news_count
    if cooccurring:
        evidence.append(
            _ev(
                "cooccurring_items",
                "Co-occurring events or news",
                cooccurring,
                run,
                source_table="event_item/news_item",
                source_ref=f"{a}:{b}:{cutoff}:{run.window_end}",
                window=f"{event_lookback} calendar days",
            )
        )
    else:
        missing.append(
            "No co-occurring stored event or news evidence was available for the last 90 days."
        )

    if portfolio_id is not None:
        risk_run = session.scalar(
            select(PortfolioRiskRun)
            .where(
                PortfolioRiskRun.portfolio_id == portfolio_id,
                PortfolioRiskRun.as_of <= run.window_end,
            )
            .order_by(desc(PortfolioRiskRun.as_of))
            .limit(1)
        )
        if risk_run is not None:
            contributions = session.scalars(
                select(PortfolioRiskContribution).where(
                    PortfolioRiskContribution.run_id == risk_run.id,
                    PortfolioRiskContribution.symbol.in_([a, b]),
                )
            ).all()
            by_symbol = {item.symbol.upper(): item for item in contributions}
            if a in by_symbol and b in by_symbol:
                for symbol in (a, b):
                    contribution = by_symbol[symbol]
                    evidence.extend(
                        [
                            _ev(
                                f"weight_{symbol}",
                                f"Portfolio weight {symbol}",
                                float(contribution.weight) * 100,
                                run,
                                source_table="portfolio_risk_contribution",
                                source_ref=f"{contribution.id}:weight",
                                unit="percent",
                            ),
                            _ev(
                                f"risk_{symbol}",
                                f"Risk contribution {symbol}",
                                float(contribution.percent_contribution),
                                run,
                                source_table="portfolio_risk_contribution",
                                source_ref=f"{contribution.id}:percent_contribution",
                                unit="percent",
                            ),
                        ]
                    )
                cluster_a = clusters_by_symbol.get(a)
                cluster_b = clusters_by_symbol.get(b)
                if cluster_a and cluster_b and cluster_a.cluster_id == cluster_b.cluster_id:
                    member_symbols = {
                        cluster.symbol.upper()
                        for cluster in clusters
                        if cluster.cluster_id == cluster_a.cluster_id
                    }
                    cluster_contributions = session.scalars(
                        select(PortfolioRiskContribution).where(
                            PortfolioRiskContribution.run_id == risk_run.id,
                            PortfolioRiskContribution.symbol.in_(member_symbols),
                        )
                    ).all()
                    cluster_risk = sum(
                        float(contribution.percent_contribution)
                        for contribution in cluster_contributions
                    )
                    evidence.append(
                        _ev(
                            "cluster_risk",
                            "Portfolio cluster risk contribution",
                            cluster_risk,
                            run,
                            source_table="portfolio_risk_contribution",
                            source_ref=f"{risk_run.id}:{cluster_a.cluster_id}",
                            unit="percent",
                        )
                    )
    return missing


def _templates(config: dict[str, Any]) -> dict[str, str]:
    value = config.get("templates")
    if not isinstance(value, dict):
        raise ValueError("mst explanation templates are missing")
    return {str(key): str(item) for key, item in value.items()}


def _sentence(
    template: str, values: dict[str, object], ids: list[str], config: dict[str, Any]
) -> ExplanationSentence | None:
    return build_sentence(template, values, ids, config)


def _base_payload(
    *,
    subject_type: str,
    subject_key: str,
    headline: str,
    evidence: list[Evidence],
    sections: list[ExplanationSection],
    config: dict[str, Any],
    limitations: list[str],
) -> ExplanationPayload:
    by_id = {item.evidence_id: item for item in evidence}
    effective_time = evidence[0].as_of
    persistence = by_id.get("persistence")
    share = _num(persistence) if persistence else 0.0
    thresholds = config["stability_thresholds"]
    level = calculate_stability_grade(
        share, float(thresholds["high"]), float(thresholds["medium"])
    ).lower()
    confidence_reason = (
        ExplanationSentence(
            text=f"Confidence is {level} from the stored-window persistence evidence.",
            evidence_ids=["persistence"],
        )
        if persistence
        else None
    )
    valid_ids = set(by_id)
    confidence_level: Literal["high", "medium", "low"]
    if level == "high":
        confidence_level = "high"
    elif level == "medium":
        confidence_level = "medium"
    else:
        confidence_level = "low"
    return ExplanationPayload(
        headline=headline,
        summary_points=[],
        sections=sections,
        evidence=evidence,
        limitations=limitations,
        confidence=ExplanationConfidence(
            level=confidence_level,
            reasons=evidence_bound_sentences(
                [confidence_reason] if confidence_reason else [], valid_ids, config
            ),
        ),
        data_age=ExplanationDataAge(
            days=evidence[0].data_age_days, as_of=effective_time, status="available"
        ),
        template_version="1.0.0",
        subject=ExplanationSubject(type=subject_type, key=subject_key),
        disclaimer=str(config["disclaimer"]),
        effective_time=effective_time,
        method="Pearson correlation, Mantegna distance, deterministic Kruskal MST",
        method_version=str(by_id["method_version"].value),
        lookback={
            "start": str(by_id["run_start"].value),
            "end": str(effective_time),
            "returns": 120,
        },
        units={"correlation": "unitless", "distance": "Mantegna distance", "beta": "return ratio"},
        thresholds=dict(thresholds),
        component_contributions=[],
        data_sufficiency="sufficient" if by_id.get("observations") else "partial",
        computed_at=datetime.fromisoformat(str(by_id["run_computed_at"].value)),
    )


class MstEdgeExplainer:
    subject_type = "mst_edge"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, MstEdgeSubject):
            raise TypeError("MstEdgeSubject required")
        run = session.get(MstRun, subject.run_id)
        if run is None or run.status != "completed":
            raise LookupError(f"completed MST run {subject.run_id} was not found")
        a, b = subject.a.upper(), subject.b.upper()
        config = _load_runtime_config(session)
        evidence, _, nodes, edges = _common_evidence(session, run, a, b, config)
        if _edge_for(edges, a, b) is None:
            raise LookupError(f"{a}-{b} is not an edge in MST run {run.id}")
        missing = _add_optional_pair_evidence(
            session, run, a, b, nodes, evidence, subject.portfolio_id, config
        )
        evidence.append(
            _ev(
                "missing_json",
                "Unavailable evidence",
                json.dumps(missing),
                run,
                source_table="mst_run",
                source_ref=f"{run.id}:availability",
                kind="config",
            )
        )
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        assert isinstance(subject, MstEdgeSubject)
        return _compose_pair_payload(
            evidence,
            config,
            template_version,
            subject.a.upper(),
            subject.b.upper(),
            self.subject_type,
            subject.key,
            edge=True,
        )


class MstPairExplainer:
    subject_type = "mst_pair"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, MstPairSubject):
            raise TypeError("MstPairSubject required")
        run = _latest_raw_run(session, as_of)
        a, b = subject.a.upper(), subject.b.upper()
        config = _load_runtime_config(session)
        evidence, _, nodes, edges = _common_evidence(session, run, a, b, config)
        path = tree_path(
            [
                (str(e.symbol_a), str(e.symbol_b), float(e.correlation or 0), float(e.distance))
                for e in edges
            ],
            a,
            b,
        )
        evidence.extend(
            [
                _ev(
                    "path_json",
                    "Tree path",
                    json.dumps(path),
                    run,
                    source_table="mst_edge",
                    source_ref=f"{run.id}:{a}:{b}:path",
                ),
                _ev(
                    "hop_count",
                    "Tree distance in links",
                    len(path),
                    run,
                    source_table="mst_edge",
                    source_ref=f"{run.id}:{a}:{b}:path",
                    unit="links",
                ),
                _ev(
                    "weakest_link",
                    "Weakest path-link correlation",
                    min(item[2] for item in path),
                    run,
                    source_table="mst_edge",
                    source_ref=f"{run.id}:{a}:{b}:path",
                ),
            ]
        )
        missing = _add_optional_pair_evidence(
            session, run, a, b, nodes, evidence, subject.portfolio_id, config
        )
        evidence.append(
            _ev(
                "missing_json",
                "Unavailable evidence",
                json.dumps(missing),
                run,
                source_table="mst_run",
                source_ref=f"{run.id}:availability",
                kind="config",
            )
        )
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        assert isinstance(subject, MstPairSubject)
        return _compose_pair_payload(
            evidence,
            config,
            template_version,
            subject.a.upper(),
            subject.b.upper(),
            self.subject_type,
            subject.key,
            edge=False,
        )


def _load_runtime_config(session: Session) -> dict[str, Any]:
    from backend.app.explain.service import load_explain_config

    return load_explain_config(session, "1.2.0", "mst_explain_templates")[0]


def _compose_pair_payload(
    evidence: list[Evidence],
    config: dict[str, Any],
    template_version: str,
    a: str,
    b: str,
    subject_type: str,
    subject_key: str,
    *,
    edge: bool,
) -> ExplanationPayload:
    by = {item.evidence_id: item for item in evidence}
    templates = _templates(config)
    values: dict[str, object] = {
        "a": a,
        "b": b,
        "correlation": round(_num(by["correlation"]), 4),
        "distance": round(_num(by["distance"]), 4),
        "rank_ab": by["rank_ab"].value,
        "rank_ba": by["rank_ba"].value,
        "observations": by["observations"].value,
        "ten_percent_effect": round(_num(by["beta"]) * 10, 2),
        "r_squared_pct": round(_num(by["r_squared"]) * 100, 2),
        "present_windows": by["present_windows"].value,
        "total_windows": by["total_windows"].value,
        "persistence_pct": round(_num(by["persistence"]) * 100, 1),
        "minimum": round(_num(by["minimum_correlation"]), 4)
        if by["minimum_correlation"].value is not None
        else None,
        "median": round(_num(by["median_correlation"]), 4)
        if by["median_correlation"].value is not None
        else None,
        "maximum": round(_num(by["maximum_correlation"]), 4)
        if by["maximum_correlation"].value is not None
        else None,
    }
    sections: list[ExplanationSection] = []
    if edge:
        values.update(
            step=by["edge_step"].value,
            edge_count=by["edge_count"].value,
            left_size=by["left_size"].value,
            right_size=by["right_size"].value,
        )
        why = [
            _sentence(
                templates["kruskal"],
                values,
                ["edge_step", "edge_count", "left_size", "right_size", "distance"],
                config,
            ),
            _sentence(templates["rank"], values, ["rank_ab", "rank_ba"], config),
        ]
        if "same_industry" in by:
            values.update(
                same_industry=str(by["same_industry"].value).lower(),
                same_cluster=str(by["same_cluster"].value).lower(),
                cluster_rule_version=by["cluster_rule"].value,
            )
            why.append(
                _sentence(
                    templates["industry_cluster"],
                    values,
                    ["same_industry", "same_cluster", "cluster_rule"],
                    config,
                )
            )
        sections.append(
            ExplanationSection(
                key="why_connected", title="Why connected", sentences=[item for item in why if item]
            )
        )
    else:
        path = json.loads(str(by["path_json"].value))
        values.update(
            hop_count=by["hop_count"].value,
            path=" → ".join([path[0][0], *[item[1] for item in path]]),
            weakest_correlation=round(_num(by["weakest_link"]), 4),
        )
        sentence = _sentence(
            templates["path"], values, ["path_json", "hop_count", "weakest_link"], config
        )
        sections.append(
            ExplanationSection(
                key="tree_path", title="Tree path", sentences=[sentence] if sentence else []
            )
        )
    strength = _sentence(templates["strength"], values, ["correlation", "distance"], config)
    sections.append(
        ExplanationSection(
            key="how_strong",
            title="How strong",
            sentences=[strength] if strength else [],
            chart_spec={
                "type": "returns_scatter",
                "x_symbol": a,
                "y_symbol": b,
                "points": json.loads(str(by["scatter_chart"].value)),
                "formula": "d = sqrt(2 * (1 - rho))",
                "distance_scale": config["distance_scale"],
            },
        )
    )
    stable_sentences = [
        _sentence(
            templates["persistence"],
            values,
            ["present_windows", "total_windows", "persistence"],
            config,
        ),
        _sentence(
            templates["rolling_range"],
            values,
            ["minimum_correlation", "median_correlation", "maximum_correlation"],
            config,
        ),
    ]
    sections.append(
        ExplanationSection(
            key="how_stable",
            title="How stable",
            sentences=[item for item in stable_sentences if item],
            chart_spec={
                "type": "rolling_correlation",
                "window": int(config["rolling_correlation_days"]),
                "points": json.loads(str(by["rolling_chart"].value)),
            },
        )
    )
    meaning = [_sentence(templates["beta"], values, ["beta", "r_squared", "observations"], config)]
    for symbol in (a, b):
        if f"degree_{symbol}" in by and f"cluster_size_{symbol}" in by:
            node_values: dict[str, object] = {
                "symbol": symbol,
                "degree": by[f"degree_{symbol}"].value,
                "centrality_percentile": round(_num(by[f"centrality_{symbol}"]), 1),
                "cluster_size": by[f"cluster_size_{symbol}"].value,
            }
            meaning.append(
                _sentence(
                    templates["node"],
                    node_values,
                    [
                        f"degree_{symbol}",
                        f"centrality_{symbol}",
                        f"cluster_size_{symbol}",
                    ],
                    config,
                )
            )
    if "residual_correlation" in by:
        values.update(
            residual_correlation=round(_num(by["residual_correlation"]), 4),
            residual_edge=str(by["residual_edge"].value).lower(),
        )
    if "macro_similarity" in by:
        values.update(
            macro_similarity=round(_num(by["macro_similarity"]), 4),
            macro_driver=by["macro_driver"].value,
        )
        meaning.append(
            _sentence(
                templates["macro"],
                values,
                ["macro_similarity", "macro_driver"],
                config,
            )
        )
    if "cooccurring_items" in by:
        values["cooccurring_items"] = by["cooccurring_items"].value
        meaning.append(_sentence(templates["cooccurring"], values, ["cooccurring_items"], config))
        meaning.append(
            _sentence(
                templates["residual"], values, ["residual_correlation", "residual_edge"], config
            )
        )
        if "cluster_risk" in by:
            values["cluster_risk"] = round(_num(by["cluster_risk"]), 2)
            meaning.append(
                _sentence(templates["cluster_portfolio"], values, ["cluster_risk"], config)
            )
    if f"weight_{a}" in by and f"weight_{b}" in by:
        values.update(
            weight_a=round(_num(by[f"weight_{a}"]), 2),
            risk_a=round(_num(by[f"risk_{a}"]), 2),
            weight_b=round(_num(by[f"weight_{b}"]), 2),
            risk_b=round(_num(by[f"risk_{b}"]), 2),
        )
        meaning.append(
            _sentence(
                templates["portfolio"],
                values,
                [f"weight_{a}", f"risk_{a}", f"weight_{b}", f"risk_{b}"],
                config,
            )
        )
    sections.append(
        ExplanationSection(
            key="what_it_means", title="What it means", sentences=[item for item in meaning if item]
        )
    )
    missing = json.loads(str(by["missing_json"].value))
    headline = templates["edge_headline" if edge else "pair_headline"].format(a=a, b=b)
    payload = _base_payload(
        subject_type=subject_type,
        subject_key=subject_key,
        headline=headline,
        evidence=evidence,
        sections=sections,
        config=config,
        limitations=missing,
    )
    return payload.model_copy(update={"template_version": template_version})


class MstNodeExplainer:
    subject_type = "mst_node"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, MstNodeSubject):
            raise TypeError("MstNodeSubject required")
        run = _latest_raw_run(session, as_of)
        symbol = subject.symbol.upper()
        nodes, edges = _run_context(session, run)
        if symbol not in nodes:
            raise LookupError(f"{symbol} is not in the stored MST")
        metric = session.scalar(
            select(MstNodeMetric).where(
                MstNodeMetric.run_id == run.id, MstNodeMetric.symbol == symbol
            )
        )
        cluster = session.scalar(
            select(MstCluster).where(MstCluster.run_id == run.id, MstCluster.symbol == symbol)
        )
        if metric is None or cluster is None:
            raise LookupError(f"diagnostics are unavailable for {symbol}")
        count = (
            session.scalar(
                select(func.count(MstNodeMetric.id)).where(MstNodeMetric.run_id == run.id)
            )
            or 1
        )
        all_metrics = session.scalars(
            select(MstNodeMetric).where(MstNodeMetric.run_id == run.id)
        ).all()
        centrality = float(metric.weighted_centrality)
        percentile = (
            100.0
            * sum(float(item.weighted_centrality) <= centrality for item in all_metrics)
            / count
        )
        cluster_peers = session.scalars(
            select(MstCluster.symbol)
            .where(
                MstCluster.run_id == run.id,
                MstCluster.cluster_id == cluster.cluster_id,
                MstCluster.symbol != symbol,
            )
            .order_by(MstCluster.symbol)
        ).all()
        neighbours = []
        for edge in edges:
            if symbol in {edge.symbol_a, edge.symbol_b}:
                other = str(edge.symbol_b if edge.symbol_a == symbol else edge.symbol_a)
                neighbours.append((other, float(edge.distance)))
        neighbours.sort(key=lambda item: (item[1], item[0]))
        return [
            _ev(
                "run_id",
                "Run ID",
                str(run.id),
                run,
                source_table="mst_run",
                source_ref=f"{run.id}:id",
            ),
            _ev(
                "run_start",
                "Run window start",
                str(run.window_start),
                run,
                source_table="mst_run",
                source_ref=f"{run.id}:window_start",
            ),
            _ev(
                "run_computed_at",
                "Run computation time",
                run.computed_at.isoformat(),
                run,
                source_table="mst_run",
                source_ref=f"{run.id}:computed_at",
            ),
            _ev(
                "method_version",
                "Layer 2 method version",
                run.implementation_version,
                run,
                source_table="mst_run",
                source_ref=f"{run.id}:implementation_version",
                kind="config",
            ),
            _ev(
                "degree",
                "Node degree",
                metric.degree,
                run,
                source_table="mst_node_metric",
                source_ref=f"{metric.id}:degree",
            ),
            _ev(
                "centrality_percentile",
                "Centrality percentile",
                percentile,
                run,
                source_table="mst_node_metric",
                source_ref=f"{metric.id}:hub_rank",
                unit="percentile",
            ),
            _ev(
                "cluster_size",
                "Cluster size",
                cluster.cluster_size,
                run,
                source_table="mst_cluster",
                source_ref=f"{cluster.id}:cluster_size",
                unit="stocks",
            ),
            _ev(
                "neighbours_json",
                "Nearest tree neighbours",
                json.dumps(neighbours[:5]),
                run,
                source_table="mst_edge",
                source_ref=f"{run.id}:{symbol}:incident",
            ),
            _ev(
                "cluster_peers",
                "Cluster peers",
                ", ".join(cluster_peers) if cluster_peers else "none",
                run,
                source_table="mst_cluster",
                source_ref=f"{run.id}:{cluster.cluster_id}:peers",
            ),
        ]

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        assert isinstance(subject, MstNodeSubject)
        by = {item.evidence_id: item for item in evidence}
        templates = _templates(config)
        role = "leaf" if by["degree"].value == 1 else "hub"
        neighbours = json.loads(str(by["neighbours_json"].value))
        values: dict[str, object] = {
            "symbol": subject.symbol.upper(),
            "node_role": role,
            "degree": by["degree"].value,
            "centrality_percentile": round(_num(by["centrality_percentile"]), 1),
            "cluster_size": by["cluster_size"].value,
            "neighbours": ", ".join(f"{name} ({distance:.3f})" for name, distance in neighbours),
        }
        facts = _sentence(
            templates["node"], values, ["degree", "centrality_percentile", "cluster_size"], config
        )
        nearest = _sentence(templates["node_neighbours"], values, ["neighbours_json"], config)
        values["cluster_peers"] = by["cluster_peers"].value
        peers = _sentence(templates["cluster_peers"], values, ["cluster_peers"], config)
        meaning = _sentence(templates["node_meaning"], values, ["degree"], config)
        sections = [
            ExplanationSection(
                key="node_facts",
                title="Why this node has its stored role",
                sentences=[item for item in [facts, nearest, peers] if item],
            ),
            ExplanationSection(
                key="what_it_means",
                title="What it means",
                sentences=[meaning] if meaning else [],
                chart_spec={
                    "type": "action_link",
                    "label": "Open shock simulator",
                    "href": f"/shock?symbol={subject.symbol.upper()}",
                },
            ),
        ]
        payload = _base_payload(
            subject_type=self.subject_type,
            subject_key=subject.key,
            headline=templates["node_headline"].format(**values),
            evidence=evidence,
            sections=sections,
            config=config,
            limitations=[],
        )
        node_confidence = ExplanationConfidence(
            level="high",
            reasons=[
                ExplanationSentence(
                    text="Stored node diagnostics are available.", evidence_ids=["degree"]
                )
            ],
        )
        return payload.model_copy(
            update={
                "template_version": template_version,
                "data_sufficiency": "sufficient",
                "confidence": node_confidence,
            }
        )


registry.register(MstEdgeExplainer())
registry.register(MstPairExplainer())
registry.register(MstNodeExplainer())
