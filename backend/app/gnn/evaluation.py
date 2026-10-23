"""Out-of-sample drift utility evaluation against transparent non-graph baselines."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from backend.app.gnn.audit import audit_dataset
from backend.app.gnn.dataset import GraphDataset, split_indices
from backend.app.gnn.learning import Scaler


def _gnn_scores(path: Path) -> dict[tuple[str, str], float]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            (row["date"], row["symbol"]): float(row["embedding_drift"])
            for row in csv.DictReader(handle)
        }


def _safe_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    return (
        float(roc_auc_score(labels, scores))
        if len(np.unique(labels)) == 2 and len(labels) > 1
        else None
    )


def _method_metrics(
    train_scores: np.ndarray,
    test_scores: np.ndarray,
    test_labels: np.ndarray,
    test_outcomes: np.ndarray,
) -> dict[str, float | int | None]:
    threshold = float(np.quantile(train_scores, 0.95))
    alerted = test_scores > threshold
    precision = float(test_labels[alerted].mean()) if alerted.any() else None
    base_rate = float(test_labels.mean())
    mean_outcome = float(test_outcomes[alerted].mean()) if alerted.any() else None
    return {
        "auc": _safe_auc(test_labels, test_scores),
        "alert_threshold": threshold,
        "alerts": int(alerted.sum()),
        "precision": precision,
        "event_base_rate": base_rate,
        "precision_lift": precision / base_rate if precision is not None and base_rate else None,
        "mean_adverse_outcome_when_alerted": mean_outcome,
    }


def evaluate(
    dataset: GraphDataset,
    stock_drift_csv: Path,
    *,
    experiment_summary: dict[str, Any] | None = None,
    minimum_auc_improvement: float = 0.02,
) -> dict[str, object]:
    """Evaluate drift as an early-warning ranking; never as a return-direction signal."""
    scores = _gnn_scores(stock_drift_csv)
    splits = split_indices(len(dataset.snapshots), dataset.config)
    scaler = Scaler.fit(dataset, int(splits["train"][-1]))
    train_ends = set(map(int, splits["train"]))
    validation_ends = set(map(int, splits["validation"]))
    test_ends = set(map(int, splits["test"]))

    train_deltas = []
    for end in sorted(train_ends):
        current, prior = dataset.snapshots[end], dataset.snapshots[end - 1]
        valid = current.active & prior.active
        train_deltas.extend((current.stock_x[valid] - prior.stock_x[valid]) / scaler.stock_std)
    delta_matrix = np.asarray(train_deltas, dtype=np.float64)
    _, _, vh = np.linalg.svd(delta_matrix - delta_matrix.mean(0), full_matrices=False)
    pca_components = vh[: min(2, delta_matrix.shape[1])]
    pca_mean = delta_matrix.mean(0)

    records: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for end in sorted(train_ends | validation_ends | test_ends):
        if end + 1 >= len(dataset.snapshots):
            continue
        current, prior, future = (
            dataset.snapshots[end],
            dataset.snapshots[end - 1],
            dataset.snapshots[end + 1],
        )
        valid = current.active & prior.active & future.active
        for stock in np.flatnonzero(valid):
            key = (current.day.isoformat(), dataset.symbols[int(stock)])
            if key not in scores:
                continue
            delta = (current.stock_x[stock] - prior.stock_x[stock]) / scaler.stock_std
            centered = delta - pca_mean
            reconstructed = (centered @ pca_components.T) @ pca_components
            history_start = max(0, end - dataset.config.sequence_length + 1)
            history = np.asarray(
                [snapshot.stock_x[stock] for snapshot in dataset.snapshots[history_start:end]],
                dtype=np.float64,
            )
            temporal = (current.stock_x[stock] - history.mean(0)) / scaler.stock_std
            industry = int(current.stock_industry[stock])
            industry_change = np.linalg.norm(
                (current.industry_x[industry] - prior.industry_x[industry]) / scaler.industry_std
            )
            market_change = np.linalg.norm(
                (current.market_x[0] - prior.market_x[0]) / scaler.market_std
            )
            adverse = max(
                abs(float(future.stock_x[stock, 0])) / float(scaler.stock_std[0]),
                max(float(future.stock_x[stock, 1] - current.stock_x[stock, 1]), 0.0)
                / float(scaler.stock_std[1]),
                max(float(current.stock_x[stock, 3] - future.stock_x[stock, 3]), 0.0)
                / float(scaler.stock_std[3]),
            )
            partition = (
                "train"
                if end in train_ends
                else "validation"
                if end in validation_ends
                else "test"
            )
            records[partition]["outcome"].append(adverse)
            records[partition]["market_volatility"].append(float(current.market_x[0, 1]))
            records[partition]["gnn"].append(scores[key])
            records[partition]["robust_feature_delta"].append(float(np.linalg.norm(delta)))
            records[partition]["pca_reconstruction"].append(
                float(np.linalg.norm(centered - reconstructed))
            )
            records[partition]["non_graph_temporal"].append(float(np.linalg.norm(temporal)))
            records[partition]["relational_aggregate"].append(
                float(np.sqrt(np.dot(delta, delta) + industry_change**2 + market_change**2))
            )

    train_outcomes = np.asarray(records["train"]["outcome"])
    validation_outcomes = np.asarray(records["validation"]["outcome"])
    test_outcomes = np.asarray(records["test"]["outcome"])
    if not len(train_outcomes) or not len(validation_outcomes) or not len(test_outcomes):
        raise ValueError("Insufficient aligned train/validation/test drift rows for evaluation")
    event_threshold = float(np.quantile(train_outcomes, 0.90))
    validation_labels = (validation_outcomes > event_threshold).astype(np.int64)
    test_labels = (test_outcomes > event_threshold).astype(np.int64)
    methods: dict[str, dict[str, Any]] = {}
    for method in (
        "gnn",
        "robust_feature_delta",
        "pca_reconstruction",
        "non_graph_temporal",
        "relational_aggregate",
    ):
        validation_metrics = _method_metrics(
            np.asarray(records["train"][method]),
            np.asarray(records["validation"][method]),
            validation_labels,
            validation_outcomes,
        )
        test_metrics = _method_metrics(
            np.asarray(records["train"][method]),
            np.asarray(records["test"][method]),
            test_labels,
            test_outcomes,
        )
        methods[method] = {
            **test_metrics,
            "validation": validation_metrics,
            "test": test_metrics,
        }
    train_market_volatility = np.asarray(records["train"]["market_volatility"])
    test_market_volatility = np.asarray(records["test"]["market_volatility"])
    low_cut, high_cut = np.quantile(train_market_volatility, (1 / 3, 2 / 3))
    regime_masks = {
        "low_volatility": test_market_volatility <= low_cut,
        "normal_volatility": (test_market_volatility > low_cut)
        & (test_market_volatility <= high_cut),
        "high_volatility": test_market_volatility > high_cut,
    }
    regime_metrics: dict[str, dict[str, dict[str, float | int | None]]] = {}
    regime_coverage_complete = True
    for regime, mask in regime_masks.items():
        if int(mask.sum()) < 100 or len(np.unique(test_labels[mask])) < 2:
            regime_coverage_complete = False
        regime_metrics[regime] = {}
        for method in methods:
            method_scores = np.asarray(records["test"][method])[mask]
            regime_labels = test_labels[mask]
            regime_metrics[regime][method] = {
                "samples": int(mask.sum()),
                "event_rate": float(regime_labels.mean()) if mask.any() else None,
                "auc": _safe_auc(regime_labels, method_scores),
            }
    baseline_aucs = [
        float(metrics["validation"]["auc"])
        for name, metrics in methods.items()
        if name != "gnn" and metrics["validation"]["auc"] is not None
    ]
    best_baseline_auc = max(baseline_aucs) if baseline_aucs else None
    gnn_auc = methods["gnn"]["validation"]["auc"]
    beats_baseline = bool(
        gnn_auc is not None
        and best_baseline_auc is not None
        and float(gnn_auc) >= best_baseline_auc + minimum_auc_improvement
    )
    experiment_summary = experiment_summary or {}
    seed_stable = bool(experiment_summary.get("seed_stable", False))
    required_ablations_complete = bool(experiment_summary.get("required_ablations_complete", False))
    data_audit = audit_dataset(dataset)
    blockers = []
    if not data_audit["production_eligible"]:
        blockers.append("point_in_time_data_audit_failed")
    if not beats_baseline:
        blockers.append("gnn_did_not_beat_best_baseline")
    if not seed_stable:
        blockers.append("multi_seed_stability_not_demonstrated")
    if not required_ablations_complete:
        blockers.append("required_ablation_experiments_not_complete")
    if not regime_coverage_complete:
        blockers.append("held_out_volatility_regime_coverage_incomplete")
    return {
        "status": "ready" if not blockers else "research_only",
        "production_eligible": not blockers,
        "blockers": blockers,
        "target": {
            "name": "next_snapshot_adverse_market_change",
            "definition": (
                "Top-decile training-period composite of absolute five-day return, "
                "volatility increase, or drawdown deterioration."
            ),
            "threshold": event_threshold,
            "not_a_direction_forecast": True,
        },
        "samples": {
            "train": len(train_outcomes),
            "validation": len(validation_outcomes),
            "test": len(test_outcomes),
        },
        "methods": methods,
        "volatility_regimes": {
            "training_tertile_cutoffs": [float(low_cut), float(high_cut)],
            "coverage_complete": regime_coverage_complete,
            "metrics": regime_metrics,
        },
        "selection": {
            "minimum_auc_improvement": minimum_auc_improvement,
            "selection_split": "validation",
            "best_baseline_validation_auc": best_baseline_auc,
            "gnn_beats_baseline": beats_baseline,
            "seed_stable": seed_stable,
            "required_ablations_complete": required_ablations_complete,
        },
        "data_audit": data_audit,
    }


def read_experiment_summary(path: Path | None) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path else None
