"""Job to calculate and persist MST diagnostics, stability, and clusters (Step 4/5)."""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime

from backend.app.correlation_mst.service import _canonical_hash
from backend.app.db.models import PipelineRun
from backend.app.db.session import SessionLocal
from backend.app.mst_diagnostics.config import load_mst_diagnostics_config
from backend.app.mst_diagnostics.history import run_mst_history_job
from backend.app.mst_diagnostics.service import (
    compute_and_persist_diagnostics,
    get_latest_mst_run_for_variant,
)


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        type=int,
        default=None,
        help="Number of historical weekly windows to evaluate (default: 26 or configured)",
    )
    parser.add_argument(
        "--anchor-date",
        type=_date,
        default=None,
        help="Anchor date for history evaluation (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--no-residual",
        action="store_true",
        help="Skip calculating the residual MST variant",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)

    with SessionLocal() as session:
        config = load_mst_diagnostics_config(session)
        history_n = args.history if args.history is not None else config.history_windows_count

        # 1. Execute rolling MST history job (computes raw and residual variants + diagnostics)
        run_residual = not args.no_residual
        history_res = run_mst_history_job(
            session=session,
            windows_count=history_n,
            run_residual=run_residual,
            anchor_date=args.anchor_date,
        )

        # 2. Also ensure diagnostics are calculated for the latest persisted raw & residual runs
        latest_raw = get_latest_mst_run_for_variant(session, "raw")
        latest_raw_diag = None
        if latest_raw is not None:
            latest_raw_diag = compute_and_persist_diagnostics(session, latest_raw.id, config=config)

        latest_res_diag = None
        if run_residual:
            latest_res = get_latest_mst_run_for_variant(session, "residual")
            if latest_res is not None:
                latest_res_diag = compute_and_persist_diagnostics(
                    session, latest_res.id, config=config
                )

        completed_at = datetime.now(UTC)

        # 3. Create pipeline_run manifest
        raw_transitions = history_res.raw_report.transitions_count
        res_transitions = (
            history_res.residual_report.transitions_count if history_res.residual_report else 0
        )
        row_counts = {
            "windows_requested": history_res.windows_requested,
            "raw_evaluated": history_res.raw_report.total_runs_evaluated,
            "raw_transitions": raw_transitions,
            "residual_evaluated": (
                history_res.residual_report.total_runs_evaluated
                if history_res.residual_report
                else 0
            ),
            "residual_transitions": res_transitions,
        }
        quality_summary = {
            "raw_average_persistence": history_res.raw_report.average_edge_persistence,
            "raw_worst_persistence": history_res.raw_report.worst_edge_persistence,
            "comparison": history_res.comparison,
            "latest_raw_run_id": str(latest_raw.id) if latest_raw else None,
            "latest_raw_grade": (latest_raw_diag.stability_grade if latest_raw_diag else None),
            "latest_residual_grade": (latest_res_diag.stability_grade if latest_res_diag else None),
        }

        cfg_hash = _canonical_hash(
            {
                "history_n": history_n,
                "cluster_k_cut": config.cluster_k_cut,
                "cluster_rule_version": config.cluster_rule_version,
                "run_residual": run_residual,
            }
        )

        run = PipelineRun(
            workflow="calculate_mst_diagnostics",
            code_version="1.0.0",
            configuration_hash=cfg_hash,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts=row_counts,
            quality_summary=quality_summary,
        )
        session.add(run)
        session.commit()

    # 4. Useful console summary
    print(f"=== MST Diagnostics Summary (history={history_n}) ===")
    print(
        f"Raw MST: evaluated={history_res.raw_report.total_runs_evaluated} windows, "
        f"transitions={history_res.raw_report.transitions_count}, "
        f"avg_persistence={history_res.raw_report.average_edge_persistence:.4f}, "
        f"worst_persistence={history_res.raw_report.worst_edge_persistence:.4f}"
    )
    if history_res.residual_report:
        delta = history_res.comparison.get("persistence_delta_residual_minus_raw", 0)
        more_stable = history_res.comparison.get("more_stable_variant")
        print(
            f"Residual MST: evaluated={history_res.residual_report.total_runs_evaluated} windows, "
            f"transitions={history_res.residual_report.transitions_count}, "
            f"avg_persistence={history_res.residual_report.average_edge_persistence:.4f}, "
            f"worst_persistence={history_res.residual_report.worst_edge_persistence:.4f}"
        )
        print(
            f"Stability comparison: more stable variant = '{more_stable}', "
            f"delta (residual - raw) = {delta:+.4f}"
        )
    if latest_raw_diag:
        print(
            f"Latest Raw Run ({latest_raw_diag.run_id}): "
            f"clusters={latest_raw_diag.clusters_count}, "
            f"node_metrics={latest_raw_diag.node_metrics_count}, "
            f"persistence={latest_raw_diag.edge_persistence}, "
            f"grade={latest_raw_diag.stability_grade}"
        )
    print("Diagnostics calculation and persistence completed successfully.")


if __name__ == "__main__":
    main()
