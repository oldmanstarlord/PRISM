"""Read-only real-data reproducibility and performance verification for Phase 0."""

import json
import time
from datetime import timedelta

from backend.app.correlation_mst.calculator import calculate_mst
from backend.app.correlation_mst.inputs import load_inputs as load_mst_inputs
from backend.app.db.session import SessionLocal
from backend.app.sector_divergence.calculator import calculate_sector_divergence
from backend.app.sector_divergence.inputs import load_inputs as load_divergence_inputs
from backend.app.sector_divergence.service import latest_market_snapshot
from backend.app.validation.reproducibility import mst_digest, sector_divergence_digest


def main() -> None:
    started = time.perf_counter()
    with SessionLocal() as session:
        market_date, cutoff = latest_market_snapshot(session)
        divergence_inputs = load_divergence_inputs(
            session, market_date, market_date - timedelta(days=180), cutoff
        )
        mst_inputs = load_mst_inputs(
            session, market_date, market_date - timedelta(days=220), cutoff
        )
    loaded = time.perf_counter()
    first_l1 = calculate_sector_divergence(divergence_inputs)
    first_l2 = calculate_mst(mst_inputs)
    first_finished = time.perf_counter()
    second_l1 = calculate_sector_divergence(divergence_inputs)
    second_l2 = calculate_mst(mst_inputs)
    second_finished = time.perf_counter()
    input_memory_bytes = int(
        divergence_inputs.adjusted_closes.memory_usage(index=True, deep=True).sum()
        + divergence_inputs.adjustment_versions.memory_usage(index=True, deep=True).sum()
        + mst_inputs.adjusted_closes.memory_usage(index=True, deep=True).sum()
        + mst_inputs.adjustment_versions.memory_usage(index=True, deep=True).sum()
    )

    l1_first_digest = sector_divergence_digest(first_l1)
    l1_second_digest = sector_divergence_digest(second_l1)
    l2_first_digest = mst_digest(first_l2)
    l2_second_digest = mst_digest(second_l2)
    if l1_first_digest != l1_second_digest or l2_first_digest != l2_second_digest:
        raise RuntimeError("Repeated calculations did not reproduce identical semantic outputs")
    if not first_l2.is_connected or not first_l2.is_acyclic:
        raise RuntimeError("Layer 2 topology validation failed")
    if len(first_l2.edges) != len(first_l2.nodes) - 1:
        raise RuntimeError("Layer 2 edge count is not N-1")

    print(
        json.dumps(
            {
                "market_date": market_date,
                "data_cutoff": cutoff,
                "layer_1_digest": l1_first_digest,
                "layer_1_scores": len(first_l1.scores),
                "layer_2_digest": l2_first_digest,
                "layer_2_nodes": len(first_l2.nodes),
                "layer_2_edges": len(first_l2.edges),
                "reproducible": True,
                "load_seconds": round(loaded - started, 3),
                "first_calculation_seconds": round(first_finished - loaded, 3),
                "second_calculation_seconds": round(second_finished - first_finished, 3),
                "input_panel_memory_mb": round(input_memory_bytes / 1024 / 1024, 3),
            },
            default=str,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
