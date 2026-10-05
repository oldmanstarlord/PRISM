"""Tests for MST stability and edge persistence calculations."""

from datetime import date
from uuid import uuid4

from backend.app.mst_diagnostics.config import MstDiagnosticsConfig
from backend.app.mst_diagnostics.stability import (
    calculate_stability_grade,
    calculate_tree_stability,
)


def test_hand_counted_edge_persistence_and_overlap() -> None:
    """Hand-calculated test case:

    Tree 1 (prior):
      Edges: (A, B), (B, C), (C, D), (D, E)  -> 4 edges
      Nodes: {A, B, C, D, E}                  -> 5 nodes

    Tree 2 (current):
      Edges: (B, A), (B, C), (C, F), (F, E)  -> 4 edges  [(B, A) == (A, B)]
      Nodes: {A, B, C, E, F}                  -> 5 nodes

    Preserved edges: (A, B) and (B, C) -> exactly 2
    Edge persistence: 2 / 4 = 0.500000

    Preserved nodes: {A, B, C, E} -> exactly 4
    Node overlap: 4 / 5 = 0.800000

    Thresholds: high=0.65, medium=0.45
    0.50 is between 0.45 and 0.65 -> Grade is "MEDIUM"
    """
    config = MstDiagnosticsConfig(
        history_windows_count=26,
        cluster_rule="remove_k_longest_edges",
        cluster_rule_version="longest-k-edges-v1",
        cluster_k_cut=10,
        threshold_high=0.65,
        threshold_medium=0.45,
        default_variant="raw",
    )

    prior_run_id = uuid4()
    current_run_id = uuid4()

    prior_edges = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]
    prior_nodes = ["A", "B", "C", "D", "E"]

    # (B, A) tested out of alphabetical order to verify canonical undirected edge equivalence
    current_edges = [("B", "A"), ("B", "C"), ("C", "F"), ("F", "E")]
    current_nodes = ["A", "B", "C", "E", "F"]

    prior_date = date(2026, 1, 15)
    current_date = date(2026, 1, 22)

    res = calculate_tree_stability(
        run_id=current_run_id,
        prior_run_id=prior_run_id,
        current_edges=current_edges,
        prior_edges=prior_edges,
        current_nodes=current_nodes,
        prior_nodes=prior_nodes,
        current_window_end=current_date,
        prior_window_end=prior_date,
        config=config,
    )

    assert res.run_id == current_run_id
    assert res.prior_run_id == prior_run_id
    assert res.edge_persistence == 0.5
    assert res.node_overlap == 0.8
    assert res.window_gap_days == 7
    assert res.grade == "MEDIUM"

    assert res.details["preserved_edge_count"] == 2
    assert res.details["current_edge_count"] == 4
    assert res.details["prior_edge_count"] == 4
    assert res.details["dropped_edge_count"] == 2
    assert res.details["new_edge_count"] == 2


def test_stability_grade_thresholds() -> None:
    assert calculate_stability_grade(0.70, 0.65, 0.45) == "HIGH"
    assert calculate_stability_grade(0.65, 0.65, 0.45) == "HIGH"
    assert calculate_stability_grade(0.649, 0.65, 0.45) == "MEDIUM"
    assert calculate_stability_grade(0.45, 0.65, 0.45) == "MEDIUM"
    assert calculate_stability_grade(0.449, 0.65, 0.45) == "LOW"
    assert calculate_stability_grade(0.0, 0.65, 0.45) == "LOW"


def test_stability_complete_preservation_and_complete_turnover() -> None:
    config = MstDiagnosticsConfig(
        history_windows_count=26,
        cluster_rule="remove_k_longest_edges",
        cluster_rule_version="longest-k-edges-v1",
        cluster_k_cut=10,
        threshold_high=0.65,
        threshold_medium=0.45,
        default_variant="raw",
    )
    edges = [("A", "B"), ("B", "C")]
    nodes = ["A", "B", "C"]

    # 100% preservation
    res_full = calculate_tree_stability(
        run_id=uuid4(),
        prior_run_id=uuid4(),
        current_edges=edges,
        prior_edges=edges,
        current_nodes=nodes,
        prior_nodes=nodes,
        current_window_end=date(2026, 2, 7),
        prior_window_end=date(2026, 1, 31),
        config=config,
    )
    assert res_full.edge_persistence == 1.0
    assert res_full.node_overlap == 1.0
    assert res_full.grade == "HIGH"

    # 0% preservation
    disjoint_edges = [("X", "Y"), ("Y", "Z")]
    disjoint_nodes = ["X", "Y", "Z"]
    res_zero = calculate_tree_stability(
        run_id=uuid4(),
        prior_run_id=uuid4(),
        current_edges=disjoint_edges,
        prior_edges=edges,
        current_nodes=disjoint_nodes,
        prior_nodes=nodes,
        current_window_end=date(2026, 2, 7),
        prior_window_end=date(2026, 1, 31),
        config=config,
    )
    assert res_zero.edge_persistence == 0.0
    assert res_zero.node_overlap == 0.0
    assert res_zero.grade == "LOW"
