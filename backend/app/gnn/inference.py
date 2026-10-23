"""Leakage-gated latest-snapshot inference for an already trained GNN."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from backend.app.gnn.analysis import _observed_drivers
from backend.app.gnn.audit import audit_dataset
from backend.app.gnn.dataset import GraphDataset
from backend.app.gnn.learning import Scaler, to_heterodata
from backend.app.gnn.model import TemporalHeteroGNN


def infer_latest(
    dataset: GraphDataset,
    run_dir: Path,
    calibration_path: Path,
    *,
    device_name: str = "cpu",
) -> dict[str, Any]:
    audit = audit_dataset(dataset)
    if not audit["production_eligible"]:
        raise ValueError(f"Dataset failed production audit: {audit['blockers']}")
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    if report["graph_config"] != dataset.config.manifest():
        raise ValueError("Inference graph configuration differs from training")
    if calibration["dataset_fingerprint"] != report["dataset_fingerprint"]:
        raise ValueError("Calibration and model fingerprints differ")
    device = torch.device(device_name)
    scaler = Scaler.read(report["scaler"])
    model = TemporalHeteroGNN(int(report["train_config"]["hidden"])).to(device)
    model.disabled_relations = tuple(report["train_config"].get("disabled_relations", ()))
    model.disabled_stock_features = tuple(report["train_config"].get("disabled_stock_features", ()))
    model.load_state_dict(
        torch.load(run_dir / "best_model.pt", map_location=device, weights_only=True)
    )
    model.eval()
    sequence = dataset.config.sequence_length

    def embedding(end: int) -> np.ndarray:
        graphs = [
            to_heterodata(
                dataset.snapshots[index],
                scaler,
                device,
                disabled_relations=frozenset(model.disabled_relations),
                disabled_stock_features=frozenset(model.disabled_stock_features),
            )
            for index in range(end - sequence + 1, end + 1)
        ]
        with torch.no_grad():
            return np.asarray(model(graphs).cpu().numpy())

    end = len(dataset.snapshots) - 1
    if end < sequence:
        raise ValueError("Insufficient snapshots for two consecutive inference sequences")
    current, prior = dataset.snapshots[end], dataset.snapshots[end - 1]
    valid = current.active & prior.active
    drift = np.linalg.norm(embedding(end) - embedding(end - 1), axis=1)
    quantile_items = sorted(
        (float(key), float(value)) for key, value in calibration["train_drift_quantiles"].items()
    )
    quantile_levels = np.asarray([item[0] for item in quantile_items])
    quantile_values = np.asarray([item[1] for item in quantile_items])
    threshold95 = float(calibration["train_drift_95pct"])
    threshold99 = float(calibration["train_drift_99pct"])
    results = []
    for stock in np.flatnonzero(valid):
        primary, scope, driver_scores = _observed_drivers(current, prior, int(stock), scaler)
        value = float(drift[stock])
        percentile = float(np.interp(value, quantile_values, quantile_levels))
        results.append(
            {
                "date": current.day.isoformat(),
                "symbol": dataset.symbols[int(stock)],
                "industry": dataset.industries[int(current.stock_industry[stock])],
                "embedding_drift": value,
                "drift_percentile": percentile,
                "alert_level": "high"
                if value > threshold99
                else "elevated"
                if value > threshold95
                else "normal",
                "primary_driver": primary,
                "driver_scope": scope,
                "driver_scores": driver_scores,
            }
        )
    return {
        "dataset_fingerprint": dataset.fingerprint,
        "training_dataset_fingerprint": report["dataset_fingerprint"],
        "date": current.day.isoformat(),
        "results": results,
        "market": {
            "date": current.day.isoformat(),
            "mean_drift": float(np.mean(drift[valid])),
            "share_above_train_95pct": float(np.mean(drift[valid] > threshold95)),
            "active_stocks": int(current.active.sum()),
        },
        "interpretation": "Descriptive structural drift; not a forecast or trade signal.",
    }
