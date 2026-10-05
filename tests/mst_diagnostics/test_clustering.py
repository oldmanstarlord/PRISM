"""Tests for deterministic MST clustering rule, tie-breaking, and node metrics."""

from uuid import uuid4

from backend.app.mst_diagnostics.clustering import (
    EdgeData,
    compute_mst_clusters_and_metrics,
)


def test_clustering_determinism_and_tie_breaking() -> None:
    """Test deterministic k-cut with identical distances on a hand-constructed tree.

    6 Nodes: A, B, C, D, E, F
    Edges:
      (A, B): distance=1.8, corr=0.1
      (B, C): distance=1.8, corr=0.1   <-- tied with (A, B)
      (C, D): distance=1.2, corr=0.4
      (D, E): distance=0.8, corr=0.6
      (E, F): distance=0.5, corr=0.8

    Tie-break rule: distance DESC, symbol_a ASC, symbol_b ASC
    With k_cut=1:
      Both (A, B) and (B, C) have distance=1.8.
      (A, B) has canonical symbols ("A", "B").
      (B, C) has canonical symbols ("B", "C").
      ("A", "B") < ("B", "C"), so (A, B) is cut first!

    Forest after cutting (A, B):
      Component 1: {A} -> size 1
      Component 2: {B, C, D, E, F} -> size 5

    Components ordered by size DESC, then min_symbol ASC:
      CLUST-01: ["B", "C", "D", "E", "F"] (size 5)
      CLUST-02: ["A"] (size 1)
    """
    symbols = ["A", "B", "C", "D", "E", "F"]
    symbols_with_ids = {sym: uuid4() for sym in symbols}

    edges = [
        EdgeData(symbol_a="B", symbol_b="A", distance=1.8, correlation=0.1, edge_rank=1),
        EdgeData(symbol_a="B", symbol_b="C", distance=1.8, correlation=0.1, edge_rank=2),
        EdgeData(symbol_a="C", symbol_b="D", distance=1.2, correlation=0.4, edge_rank=3),
        EdgeData(symbol_a="D", symbol_b="E", distance=0.8, correlation=0.6, edge_rank=4),
        EdgeData(symbol_a="E", symbol_b="F", distance=0.5, correlation=0.8, edge_rank=5),
    ]

    res = compute_mst_clusters_and_metrics(
        symbols_with_ids=symbols_with_ids,
        edges=edges,
        k_cut=1,
        cluster_rule_version="longest-k-edges-v1",
    )

    assert len(res.cut_edges) == 1
    assert res.cut_edges[0][0] == "A"
    assert res.cut_edges[0][1] == "B"
    assert res.cut_edges[0][2] == 1.8

    assert len(res.clusters) == 2
    assert res.clusters["CLUST-01"] == ["B", "C", "D", "E", "F"]
    assert res.clusters["CLUST-02"] == ["A"]

    # Verify assignments
    asgn_map = {a.symbol: a for a in res.assignments}
    assert asgn_map["A"].cluster_id == "CLUST-02"
    assert asgn_map["A"].cluster_size == 1
    assert asgn_map["B"].cluster_id == "CLUST-01"
    assert asgn_map["B"].cluster_size == 5


def test_node_metrics_degree_centrality_and_hub_rank() -> None:
    """Test node metrics calculation and hub ranking.

    Tree: Star topology centered at 'HUB' connected to S1, S2, S3, S4
      (HUB, S1): distance=0.5, corr=0.8
      (HUB, S2): distance=0.6, corr=0.7
      (HUB, S3): distance=0.7, corr=0.6
      (HUB, S4): distance=0.8, corr=0.5
      (S4, S5):  distance=1.0, corr=0.3

    Degrees:
      HUB: 4 incident edges, centrality = 0.8 + 0.7 + 0.6 + 0.5 = 2.6
      S4:  2 incident edges (HUB, S5), centrality = 0.5 + 0.3 = 0.8
      S1:  1 incident edge (HUB), centrality = 0.8
      S2:  1 incident edge (HUB), centrality = 0.7
      S3:  1 incident edge (HUB), centrality = 0.6
      S5:  1 incident edge (S4), centrality = 0.3

    Hub Ranks (degree DESC, centrality DESC, symbol ASC):
      Rank 1: HUB (deg 4)
      Rank 2: S4  (deg 2)
      Rank 3: S1  (deg 1, cent 0.8)
      Rank 4: S2  (deg 1, cent 0.7)
      Rank 5: S3  (deg 1, cent 0.6)
      Rank 6: S5  (deg 1, cent 0.3)
    """
    symbols = ["HUB", "S1", "S2", "S3", "S4", "S5"]
    symbols_with_ids = {sym: uuid4() for sym in symbols}

    edges = [
        EdgeData(symbol_a="HUB", symbol_b="S1", distance=0.5, correlation=0.8, edge_rank=1),
        EdgeData(symbol_a="HUB", symbol_b="S2", distance=0.6, correlation=0.7, edge_rank=2),
        EdgeData(symbol_a="HUB", symbol_b="S3", distance=0.7, correlation=0.6, edge_rank=3),
        EdgeData(symbol_a="HUB", symbol_b="S4", distance=0.8, correlation=0.5, edge_rank=4),
        EdgeData(symbol_a="S4", symbol_b="S5", distance=1.0, correlation=0.3, edge_rank=5),
    ]

    res = compute_mst_clusters_and_metrics(
        symbols_with_ids=symbols_with_ids,
        edges=edges,
        k_cut=2,
    )

    metric_map = {m.symbol: m for m in res.node_metrics}

    assert metric_map["HUB"].degree == 4
    assert metric_map["HUB"].weighted_centrality == 2.6
    assert metric_map["HUB"].hub_rank == 1

    assert metric_map["S4"].degree == 2
    assert metric_map["S4"].weighted_centrality == 0.8
    assert metric_map["S4"].hub_rank == 2

    assert metric_map["S1"].degree == 1
    assert metric_map["S1"].hub_rank == 3

    assert metric_map["S2"].degree == 1
    assert metric_map["S2"].hub_rank == 4

    assert metric_map["S3"].degree == 1
    assert metric_map["S3"].hub_rank == 5

    assert metric_map["S5"].degree == 1
    assert metric_map["S5"].hub_rank == 6
