"""MST stability and edge persistence calculations across consecutive windows."""

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from backend.app.mst_diagnostics.config import MstDiagnosticsConfig


@dataclass(frozen=True, slots=True)
class TreeEdge:
    symbol_a: str
    symbol_b: str

    @classmethod
    def canonical(cls, sym_a: str, sym_b: str) -> "TreeEdge":
        if sym_a <= sym_b:
            return cls(sym_a, sym_b)
        return cls(sym_b, sym_a)

    def to_tuple(self) -> tuple[str, str]:
        return (self.symbol_a, self.symbol_b)


@dataclass(frozen=True, slots=True)
class StabilityResult:
    run_id: UUID
    prior_run_id: UUID
    edge_persistence: float
    node_overlap: float
    window_gap_days: int
    grade: str
    details: dict[str, Any]


def calculate_stability_grade(
    edge_persistence: float,
    threshold_high: float = 0.65,
    threshold_medium: float = 0.45,
) -> str:
    """Classify stability into HIGH, MEDIUM, or LOW according to config thresholds."""
    if edge_persistence >= threshold_high:
        return "HIGH"
    if edge_persistence >= threshold_medium:
        return "MEDIUM"
    return "LOW"


def calculate_tree_stability(
    *,
    run_id: UUID,
    prior_run_id: UUID,
    current_edges: list[tuple[str, str]],
    prior_edges: list[tuple[str, str]],
    current_nodes: list[str],
    prior_nodes: list[str],
    current_window_end: date,
    prior_window_end: date,
    config: MstDiagnosticsConfig,
) -> StabilityResult:
    """Calculate edge persistence, node overlap, and stability grade between two MST trees."""
    curr_e_set = {TreeEdge.canonical(a, b).to_tuple() for a, b in current_edges}
    prior_e_set = {TreeEdge.canonical(a, b).to_tuple() for a, b in prior_edges}

    curr_v_set = set(current_nodes)
    prior_v_set = set(prior_nodes)

    preserved_edges = sorted(curr_e_set & prior_e_set)
    new_edges = sorted(curr_e_set - prior_e_set)
    dropped_edges = sorted(prior_e_set - curr_e_set)

    edge_persistence = len(preserved_edges) / len(curr_e_set) if curr_e_set else 0.0
    node_overlap = len(curr_v_set & prior_v_set) / len(curr_v_set) if curr_v_set else 0.0
    window_gap_days = max(0, (current_window_end - prior_window_end).days)

    grade = calculate_stability_grade(
        edge_persistence,
        threshold_high=config.threshold_high,
        threshold_medium=config.threshold_medium,
    )

    details = {
        "current_edge_count": len(curr_e_set),
        "prior_edge_count": len(prior_e_set),
        "preserved_edge_count": len(preserved_edges),
        "new_edge_count": len(new_edges),
        "dropped_edge_count": len(dropped_edges),
        "current_node_count": len(curr_v_set),
        "prior_node_count": len(prior_v_set),
        "preserved_node_count": len(curr_v_set & prior_v_set),
        "preserved_edges_sample": preserved_edges[:10],
    }

    return StabilityResult(
        run_id=run_id,
        prior_run_id=prior_run_id,
        edge_persistence=round(edge_persistence, 6),
        node_overlap=round(node_overlap, 6),
        window_gap_days=window_gap_days,
        grade=grade,
        details=details,
    )
