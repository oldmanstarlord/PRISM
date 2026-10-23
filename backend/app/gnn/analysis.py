"""Descriptive embedding-change analysis, not a forecast or trade signal."""

import csv
import json
from pathlib import Path

import numpy as np
import torch

from backend.app.gnn.config import STOCK_FEATURES
from backend.app.gnn.dataset import GraphDataset, Snapshot, split_indices
from backend.app.gnn.learning import Scaler, to_heterodata
from backend.app.gnn.model import TemporalHeteroGNN


def _edge_churn(current: np.ndarray, prior: np.ndarray) -> float:
    current_set = {tuple(sorted(map(int, pair))) for pair in current.tolist()}
    prior_set = {tuple(sorted(map(int, pair))) for pair in prior.tolist()}
    union = current_set | prior_set
    return 0.0 if not union else 1.0 - len(current_set & prior_set) / len(union)


def _observed_drivers(
    current: Snapshot, prior: Snapshot, stock: int, scaler: Scaler
) -> tuple[str, str, dict[str, float]]:
    """Explain observed input change without claiming learned causal attribution."""
    stock_changes = np.abs((current.stock_x[stock] - prior.stock_x[stock]) / scaler.stock_std)
    scores = {name: float(stock_changes[index]) for index, name in enumerate(STOCK_FEATURES)}
    scores["mst_relationship_churn"] = _edge_churn(current.mst_edges, prior.mst_edges)
    scores["correlation_relationship_churn"] = _edge_churn(
        current.correlation_edges, prior.correlation_edges
    )
    industry = int(current.stock_industry[stock])
    if industry < len(prior.industry_x):
        scores["industry_context_change"] = float(
            np.linalg.norm(
                (current.industry_x[industry] - prior.industry_x[industry]) / scaler.industry_std
            )
        )
    scores["market_context_change"] = float(
        np.linalg.norm((current.market_x[0] - prior.market_x[0]) / scaler.market_std)
    )
    primary = max(scores, key=scores.__getitem__)
    scope = (
        "market"
        if primary == "market_context_change"
        else "industry"
        if primary == "industry_context_change"
        else "relationship"
        if primary.endswith("relationship_churn")
        else "stock"
    )
    return primary, scope, scores


def analyze(
    dataset: GraphDataset, run: Path, output: Path, *, device_name: str = "cpu"
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    if report["dataset_fingerprint"] != dataset.fingerprint:
        raise ValueError("Dataset fingerprint does not match the trained checkpoint")
    device = torch.device(device_name)
    scaler = Scaler.read(report["scaler"])
    model = TemporalHeteroGNN(int(report["train_config"]["hidden"])).to(device)
    model.disabled_relations = tuple(report["train_config"].get("disabled_relations", ()))
    model.disabled_stock_features = tuple(report["train_config"].get("disabled_stock_features", ()))
    model.load_state_dict(torch.load(run / "best_model.pt", map_location=device, weights_only=True))
    model.eval()
    embeddings = []
    with torch.no_grad():
        for end in range(dataset.config.sequence_length - 1, len(dataset.snapshots)):
            graphs = [
                to_heterodata(
                    dataset.snapshots[index],
                    scaler,
                    device,
                    disabled_relations=frozenset(model.disabled_relations),
                    disabled_stock_features=frozenset(model.disabled_stock_features),
                )
                for index in range(end - dataset.config.sequence_length + 1, end + 1)
            ]
            embeddings.append(model(graphs).cpu().numpy())
    split = split_indices(len(dataset.snapshots), dataset.config)
    first = dataset.config.sequence_length - 1
    # Calibrate drift only on differences fully inside the training period.
    calibration = []
    for end in split["train"][1:]:
        current, prior = dataset.snapshots[int(end)], dataset.snapshots[int(end - 1)]
        valid = current.active & prior.active
        delta = np.linalg.norm(
            embeddings[int(end) - first][valid] - embeddings[int(end) - first - 1][valid], axis=1
        )
        calibration.extend(delta.tolist())
    if not calibration:
        raise ValueError(
            "Insufficient consecutive train-period stock observations for drift calibration"
        )
    threshold = float(np.quantile(calibration, 0.95))
    high_threshold = float(np.quantile(calibration, 0.99))
    calibration_array = np.sort(np.asarray(calibration, dtype=np.float64))
    output.mkdir(parents=True)
    rows = []
    summary = []
    for end in range(first + 1, len(dataset.snapshots)):
        current, prior = dataset.snapshots[end], dataset.snapshots[end - 1]
        valid = current.active & prior.active
        drift = np.linalg.norm(embeddings[end - first] - embeddings[end - first - 1], axis=1)
        summary.append(
            {
                "date": current.day.isoformat(),
                "mean_drift": float(np.mean(drift[valid])) if valid.any() else None,
                "share_above_train_95pct": float(np.mean(drift[valid] > threshold))
                if valid.any()
                else None,
                "active_stocks": int(current.active.sum()),
            }
        )
        for stock in np.flatnonzero(valid):
            percentile = float(
                np.searchsorted(calibration_array, drift[stock], side="right")
                / len(calibration_array)
            )
            primary_driver, driver_scope, driver_scores = _observed_drivers(
                current, prior, int(stock), scaler
            )
            rows.append(
                {
                    "date": current.day.isoformat(),
                    "symbol": dataset.symbols[stock],
                    "industry": dataset.industries[current.stock_industry[stock]],
                    "embedding_drift": float(drift[stock]),
                    "drift_percentile": percentile,
                    "above_train_95pct": bool(drift[stock] > threshold),
                    "alert_level": (
                        "high"
                        if drift[stock] > high_threshold
                        else "elevated"
                        if drift[stock] > threshold
                        else "normal"
                    ),
                    "primary_driver": primary_driver,
                    "driver_scope": driver_scope,
                    "driver_scores": json.dumps(driver_scores, sort_keys=True),
                }
            )
    with (output / "stock_drift.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "date",
                "symbol",
                "industry",
                "embedding_drift",
                "drift_percentile",
                "above_train_95pct",
                "alert_level",
                "primary_driver",
                "driver_scope",
                "driver_scores",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    with (output / "market_drift.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["date", "mean_drift", "share_above_train_95pct", "active_stocks"]
        )
        writer.writeheader()
        writer.writerows(summary)
    result: dict[str, object] = {
        "dataset_fingerprint": dataset.fingerprint,
        "run": str(run),
        "train_drift_95pct": threshold,
        "train_drift_99pct": high_threshold,
        "train_drift_quantiles": {
            f"{quantile:.2f}": float(np.quantile(calibration_array, quantile))
            for quantile in np.linspace(0, 1, 101)
        },
        "snapshots": len(summary),
        "interpretation": (
            "Descriptive embedding change; not a calibrated risk probability, "
            "forecast, or trade signal."
        ),
        "driver_interpretation": (
            "Drivers describe the largest observed normalized input or relation change; "
            "they are diagnostics, not causal attributions."
        ),
    }
    (output / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
