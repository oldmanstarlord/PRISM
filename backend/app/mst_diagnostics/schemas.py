"""Pydantic schemas and typed dataclasses for MST diagnostics."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MstStabilitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    prior_run_id: UUID
    edge_persistence: float = Field(
        ..., description="Fraction of edges preserved: |E_t ∩ E_t-1| / |E_t|"
    )
    node_overlap: float = Field(
        ..., description="Fraction of nodes present in both trees: |V_t ∩ V_t-1| / |V_t|"
    )
    window_gap_days: int = Field(
        ..., description="Calendar day gap between consecutive window ends"
    )
    grade: str = Field(
        ..., description="Stability grade: HIGH (>=65%), MEDIUM (>=45%), or LOW (<45%)"
    )
    details: dict[str, Any] = Field(default_factory=dict)


class MstStabilityLatestResponse(BaseModel):
    latest_stability: MstStabilitySummary | None = None
    history_summary: dict[str, Any] = Field(
        default_factory=lambda: {
            "windows_evaluated": 0,
            "average_edge_persistence": 0.0,
            "worst_edge_persistence": 0.0,
            "worst_window": None,
            "thresholds": {"high": 0.65, "medium": 0.45},
        }
    )
    raw_vs_residual_comparison: dict[str, Any] | None = None
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Stability measures persistence across consecutive rolling windows, not optimality.",
            "High persistence does not imply causal connection or invariant economic links.",
            "Changes in universe eligibility or corporate actions naturally introduce turnover.",
        ]
    )


class MstClusterMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    security_id: UUID
    symbol: str
    cluster_id: str
    cluster_size: int
    cluster_rule_version: str


class MstClustersResponse(BaseModel):
    run_id: UUID
    cluster_rule_version: str
    cluster_k_cut: int
    clusters_count: int
    clusters: dict[str, list[str]] = Field(..., description="Map of cluster_id to symbol list")
    members: list[MstClusterMember]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Clusters are formed deterministically by cutting the k-longest edges of the MST.",
            "Clusters represent co-movement subgraphs, not fundamental industrial classifications.",
            "A stock outside a cluster may still have positive correlation to its members.",
        ]
    )


class IncidentEdge(BaseModel):
    neighbor_symbol: str
    correlation: float
    distance: float
    edge_rank: int


class MstNodeMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    security_id: UUID
    symbol: str
    run_id: UUID
    degree: int
    weighted_centrality: float
    hub_rank: int
    cluster_id: str | None = None
    cluster_size: int | None = None
    cluster_peers: list[str] = Field(default_factory=list)
    incident_edges: list[IncidentEdge] = Field(default_factory=list)
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Degree and centrality reflect tree topology, not corporate systemic importance.",
            "Hub nodes summarize correlation networks; their position is descriptive.",
        ]
    )


class MstNodeSummary(BaseModel):
    id: str
    symbol: str
    industry: str
    observations_used: int
    degree: int | None = None
    weighted_centrality: float | None = None
    hub_rank: int | None = None
    cluster_id: str | None = None


class MstEdgeSummary(BaseModel):
    source: str
    target: str
    symbol_a: str
    symbol_b: str
    correlation: float | None
    distance: float
    paired_observations: int
    edge_rank: int


class MstRunSummary(BaseModel):
    id: str
    window_start: date
    window_end: date
    data_cutoff: datetime | None
    requested_symbol_count: int
    included_symbol_count: int
    edge_count: int
    is_connected: bool
    is_acyclic: bool
    implementation_version: str
    variant: str = "raw"
    configuration: dict[str, Any]
    computed_at: datetime
    exclusions: list[dict[str, Any]] = Field(default_factory=list)


class MstLatestResponse(BaseModel):
    run: MstRunSummary
    variant: str = "raw"
    stability_grade: str | None = None
    edge_persistence: float | None = None
    clusters_count: int | None = None
    nodes: list[MstNodeSummary]
    edges: list[MstEdgeSummary]
    limitations: list[str]
