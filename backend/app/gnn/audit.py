"""Deterministic data/readiness gates for temporal GNN artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from backend.app.gnn.dataset import GraphDataset, split_indices


@dataclass(frozen=True)
class AuditCheck:
    name: str
    passed: bool
    severity: str
    detail: str


def audit_dataset(dataset: GraphDataset) -> dict[str, object]:
    snapshots = dataset.snapshots
    splits = split_indices(len(snapshots), dataset.config)
    active_counts = np.asarray([int(snapshot.active.sum()) for snapshot in snapshots])
    dates = [snapshot.day for snapshot in snapshots]
    finite = all(
        np.isfinite(snapshot.stock_x[snapshot.active]).all()
        and np.isfinite(snapshot.industry_x).all()
        and np.isfinite(snapshot.market_x).all()
        for snapshot in snapshots
    )
    unique_dates = len(set(dates)) == len(dates)
    strictly_ordered = all(left < right for left, right in zip(dates, dates[1:], strict=False))
    point_in_time = dataset.universe_mode == "source_time_filtered_historical_industry"
    checks = [
        AuditCheck(
            "point_in_time_inputs",
            point_in_time,
            "blocker",
            (
                "Membership, aliases, price revisions, volumes and industry classifications "
                "are filtered by their source-time availability."
                if point_in_time
                else "Retrospective/current-universe inputs create survivorship or revision bias."
            ),
        ),
        AuditCheck("unique_snapshot_dates", unique_dates, "blocker", "Snapshot dates are unique."),
        AuditCheck(
            "ordered_snapshot_dates", strictly_ordered, "blocker", "Snapshot dates are ordered."
        ),
        AuditCheck(
            "finite_active_features", finite, "blocker", "Active graph features are finite."
        ),
        AuditCheck(
            "minimum_graph_coverage",
            bool((active_counts >= dataset.config.min_stocks).all()),
            "blocker",
            f"Minimum/median active stocks: {active_counts.min()}/{np.median(active_counts):.0f}.",
        ),
        AuditCheck(
            "chronological_embargo",
            all(
                int(right[0]) - int(left[-1]) > dataset.config.embargo_snapshots
                for left, right in (
                    (splits["train"], splits["validation"]),
                    (splits["validation"], splits["test"]),
                )
            ),
            "blocker",
            "Train, validation and test windows are separated by the configured embargo.",
        ),
    ]
    blockers = [check.name for check in checks if check.severity == "blocker" and not check.passed]
    return {
        "production_eligible": not blockers,
        "blockers": blockers,
        "checks": [asdict(check) for check in checks],
        "coverage": {
            "first_snapshot": dates[0].isoformat(),
            "last_snapshot": dates[-1].isoformat(),
            "snapshots": len(snapshots),
            "symbols": len(dataset.symbols),
            "min_active_stocks": int(active_counts.min()),
            "median_active_stocks": float(np.median(active_counts)),
        },
    }
