"""Deterministic clustering and node metrics for correlation MST."""

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EdgeData:
    symbol_a: str
    symbol_b: str
    distance: float
    correlation: float
    edge_rank: int

    @property
    def canonical_symbols(self) -> tuple[str, str]:
        return (min(self.symbol_a, self.symbol_b), max(self.symbol_a, self.symbol_b))


@dataclass(frozen=True, slots=True)
class ClusterAssignment:
    security_id: UUID
    symbol: str
    cluster_id: str
    cluster_rule_version: str
    cluster_size: int


@dataclass(frozen=True, slots=True)
class NodeMetricResult:
    security_id: UUID
    symbol: str
    degree: int
    weighted_centrality: float
    hub_rank: int


@dataclass(frozen=True, slots=True)
class ClusteringResult:
    cluster_rule_version: str
    k_cut: int
    clusters: dict[str, list[str]]  # cluster_id -> sorted list of symbols
    assignments: list[ClusterAssignment]
    node_metrics: list[NodeMetricResult]
    cut_edges: list[tuple[str, str, float]]


class _DisjointSet:
    def __init__(self, elements: list[str]) -> None:
        self.parent = {el: el for el in elements}
        self.rank = {el: 0 for el in elements}

    def find(self, item: str) -> str:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            nxt = self.parent[item]
            self.parent[item] = root
            item = nxt
        return root

    def union(self, a: str, b: str) -> bool:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


def compute_mst_clusters_and_metrics(
    *,
    symbols_with_ids: dict[str, UUID],
    edges: list[EdgeData],
    k_cut: int = 10,
    cluster_rule_version: str = "longest-k-edges-v1",
) -> ClusteringResult:
    """Deterministically segment the MST by removing k longest edges and compute node metrics."""
    all_symbols = sorted(symbols_with_ids.keys())

    # 1. Compute node degree and weighted centrality on full MST
    incident_correlations: dict[str, list[float]] = defaultdict(list)
    for edge in edges:
        incident_correlations[edge.symbol_a].append(edge.correlation)
        incident_correlations[edge.symbol_b].append(edge.correlation)

    raw_metrics: list[tuple[int, float, str, UUID]] = []
    for sym in all_symbols:
        sec_id = symbols_with_ids[sym]
        corrs = incident_correlations.get(sym, [])
        deg = len(corrs)
        centrality = round(sum(corrs), 6) if corrs else 0.0
        raw_metrics.append((deg, centrality, sym, sec_id))

    # Sort nodes for hub rank: degree DESC, weighted_centrality DESC, symbol ASC
    raw_metrics.sort(key=lambda item: (-item[0], -item[1], item[2]))

    node_metrics: list[NodeMetricResult] = [
        NodeMetricResult(
            security_id=sec_id,
            symbol=sym,
            degree=deg,
            weighted_centrality=centrality,
            hub_rank=rank + 1,
        )
        for rank, (deg, centrality, sym, sec_id) in enumerate(raw_metrics)
    ]

    # 2. Sort edges by distance DESC, with deterministic tie-breaking (symbol_a ASC, symbol_b ASC)
    sorted_edges = sorted(
        edges,
        key=lambda e: (
            -e.distance,
            e.canonical_symbols[0],
            e.canonical_symbols[1],
        ),
    )

    actual_k = min(k_cut, len(sorted_edges))
    cut_edge_objs = sorted_edges[:actual_k]
    cut_edge_tuples = [
        (e.canonical_symbols[0], e.canonical_symbols[1], round(e.distance, 6))
        for e in cut_edge_objs
    ]
    cut_set = {e.canonical_symbols for e in cut_edge_objs}

    # 3. Form connected components with remaining edges
    dsu = _DisjointSet(all_symbols)
    for edge in edges:
        canon = edge.canonical_symbols
        if canon not in cut_set:
            dsu.union(canon[0], canon[1])

    components: dict[str, list[str]] = defaultdict(list)
    for sym in all_symbols:
        root = dsu.find(sym)
        components[root].append(sym)

    # Sort components deterministically: size DESC, then smallest symbol ASC
    sorted_components = sorted(
        components.values(),
        key=lambda members: (-len(members), sorted(members)[0]),
    )

    clusters: dict[str, list[str]] = {}
    assignments: list[ClusterAssignment] = []

    for idx, member_list in enumerate(sorted_components):
        cluster_id = f"CLUST-{idx + 1:02d}"
        sorted_members = sorted(member_list)
        clusters[cluster_id] = sorted_members
        c_size = len(sorted_members)
        for sym in sorted_members:
            assignments.append(
                ClusterAssignment(
                    security_id=symbols_with_ids[sym],
                    symbol=sym,
                    cluster_id=cluster_id,
                    cluster_rule_version=cluster_rule_version,
                    cluster_size=c_size,
                )
            )

    return ClusteringResult(
        cluster_rule_version=cluster_rule_version,
        k_cut=actual_k,
        clusters=clusters,
        assignments=assignments,
        node_metrics=node_metrics,
        cut_edges=cut_edge_tuples,
    )
