"""Persist immutable GNN research outputs with model and data provenance."""

import csv
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import GnnMarketDrift, GnnStockDrift, ModelRun
from backend.app.gnn.config import STOCK_FEATURES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def publish_analysis(
    session: Session,
    run_dir: Path,
    analysis_dir: Path,
    evaluation_path: Path,
) -> ModelRun:
    report: dict[str, Any] = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    analysis: dict[str, Any] = json.loads(
        (analysis_dir / "analysis.json").read_text(encoding="utf-8")
    )
    evaluation: dict[str, Any] = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if report["dataset_fingerprint"] != analysis["dataset_fingerprint"]:
        raise ValueError("Training and analysis dataset fingerprints differ")
    version = f"{report['dataset_fingerprint'][:12]}-{report['split_dates']['test'][1]}"
    existing = session.scalar(
        select(ModelRun).where(
            ModelRun.model_name == "temporal_hetero_gnn",
            ModelRun.model_version == version,
        )
    )
    if existing is not None:
        raise ValueError(f"GNN model version {version} has already been published")
    production_eligible = bool(evaluation.get("production_eligible", False))
    split_dates = report["split_dates"]
    model_run = ModelRun(
        model_name="temporal_hetero_gnn",
        model_version=version,
        model_type="temporal_heterogeneous_graphsage_gru",
        methodology_version="prism-temporal-hetero-v1",
        feature_schema_version="prism-temporal-hetero-v1",
        source_data_version=report["dataset_fingerprint"],
        data_cutoff=datetime.fromisoformat(
            report.get("data_cutoff", datetime.now(UTC).isoformat())
        ),
        training_window_start=date.fromisoformat(split_dates["train"][0]),
        training_window_end=date.fromisoformat(split_dates["train"][1]),
        validation_window_start=date.fromisoformat(split_dates["validation"][0]),
        validation_window_end=date.fromisoformat(split_dates["validation"][1]),
        test_window_start=date.fromisoformat(split_dates["test"][0]),
        test_window_end=date.fromisoformat(split_dates["test"][1]),
        features=list(STOCK_FEATURES),
        hyperparameters=report["train_config"],
        preprocessing={
            "graph_config": report["graph_config"],
            "scaler": report["scaler"],
            "universe_mode": report["universe_mode"],
        },
        metrics={"reconstruction_test": report["test"], "drift_evaluation": evaluation},
        baseline_comparison=evaluation.get("methods", {}),
        configuration_hash=report["dataset_fingerprint"],
        status="ready" if production_eligible else "completed",
        trained_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        artifact_path=str(run_dir),
        artifact_checksum=_sha256(run_dir / "best_model.pt"),
        model_selected="temporal_hetero_gnn" if production_eligible else None,
        selection_reason=(
            "Passed point-in-time, baseline, multi-seed and relation-ablation gates."
            if production_eligible
            else "; ".join(map(str, evaluation.get("blockers", ["research_only"])))
        ),
    )
    session.add(model_run)
    session.flush()
    with (analysis_dir / "stock_drift.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            session.add(
                GnnStockDrift(
                    run_id=model_run.id,
                    analysis_date=date.fromisoformat(row["date"]),
                    symbol=row["symbol"],
                    industry=row["industry"],
                    embedding_drift=Decimal(row["embedding_drift"]),
                    drift_percentile=Decimal(row["drift_percentile"]),
                    alert_level=row["alert_level"],
                    primary_driver=row.get("primary_driver") or None,
                    driver_scope=row.get("driver_scope") or None,
                    driver_scores=json.loads(row.get("driver_scores") or "{}"),
                    explanation={
                        "kind": "observed_input_change",
                        "causal": False,
                        "forecast": False,
                    },
                )
            )
    with (analysis_dir / "market_drift.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row["mean_drift"]:
                continue
            session.add(
                GnnMarketDrift(
                    run_id=model_run.id,
                    analysis_date=date.fromisoformat(row["date"]),
                    mean_drift=Decimal(row["mean_drift"]),
                    share_above_train_95pct=Decimal(row["share_above_train_95pct"]),
                    active_stocks=int(row["active_stocks"]),
                )
            )
    return model_run


def persist_latest_inference(session: Session, run_dir: Path, payload: dict[str, Any]) -> ModelRun:
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    run = session.scalar(
        select(ModelRun)
        .where(
            ModelRun.model_name == "temporal_hetero_gnn",
            ModelRun.source_data_version == report["dataset_fingerprint"],
        )
        .order_by(ModelRun.trained_at.desc())
        .limit(1)
    )
    if run is None or run.status != "ready":
        raise ValueError("Only a published, validation-gated GNN run may receive weekly inference")
    analysis_date = date.fromisoformat(str(payload["date"]))
    for row in payload["results"]:
        exists = session.scalar(
            select(GnnStockDrift.id).where(
                GnnStockDrift.run_id == run.id,
                GnnStockDrift.analysis_date == analysis_date,
                GnnStockDrift.symbol == row["symbol"],
            )
        )
        if exists is not None:
            continue
        session.add(
            GnnStockDrift(
                run_id=run.id,
                analysis_date=analysis_date,
                symbol=row["symbol"],
                industry=row["industry"],
                embedding_drift=Decimal(str(row["embedding_drift"])),
                drift_percentile=Decimal(str(row["drift_percentile"])),
                alert_level=row["alert_level"],
                primary_driver=row.get("primary_driver"),
                driver_scope=row.get("driver_scope"),
                driver_scores=row.get("driver_scores", {}),
                explanation={"kind": "observed_input_change", "causal": False, "forecast": False},
            )
        )
    market = payload["market"]
    market_exists = session.scalar(
        select(GnnMarketDrift.id).where(
            GnnMarketDrift.run_id == run.id,
            GnnMarketDrift.analysis_date == analysis_date,
        )
    )
    if market_exists is None:
        session.add(
            GnnMarketDrift(
                run_id=run.id,
                analysis_date=analysis_date,
                mean_drift=Decimal(str(market["mean_drift"])),
                share_above_train_95pct=Decimal(str(market["share_above_train_95pct"])),
                active_stocks=int(market["active_stocks"]),
            )
        )
    return run
