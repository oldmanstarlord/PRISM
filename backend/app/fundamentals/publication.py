"""Publish a complete dated generation atomically; retain last success on failure."""

from __future__ import annotations

import csv
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from backend.app.fundamentals.data import BASE_NUMERIC, POLICY_VERSION, clean_rows, sha256
from backend.app.fundamentals.training import predict_rows

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLICATION = ROOT / "data/processed/fundamentals/live"
DEFAULT_MODEL = ROOT / "data/models/fundamentals/2026-10-05/model.joblib"
ACTIVE_MODEL_POINTER = ROOT / "data/models/fundamentals/active_model.json"


def resolve_model_path(requested: Path, pointer: Path = ACTIVE_MODEL_POINTER) -> Path:
    """Use a verified active advisory model; explicit model overrides remain explicit."""
    if requested != DEFAULT_MODEL or not pointer.exists():
        return requested
    metadata = json.loads(pointer.read_text())
    relative = metadata["path"]
    if not isinstance(relative, str):
        raise ValueError("Active model path must be a string")
    candidate = (ROOT / relative).resolve()
    allowed = (ROOT / "data/models/fundamentals").resolve()
    if not candidate.is_relative_to(allowed):
        raise ValueError("Active model path outside fundamentals model directory")
    if sha256(candidate) != metadata["sha256"]:
        raise ValueError("Active model checksum mismatch; publication stopped")
    return candidate


def atomic_json(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(content, indent=2, allow_nan=False))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def run_lock(root: Path) -> Iterator[None]:
    """OS advisory lock is released even if a process is interrupted."""
    import fcntl

    root.mkdir(parents=True, exist_ok=True)
    with (root / ".refresh.lock").open("a") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Fundamentals refresh already running") from exc
        try:
            yield
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


def read_latest(root: Path = DEFAULT_PUBLICATION) -> dict[str, Any]:
    pointer = json.loads((root / "latest.json").read_text())
    generation = pointer["generation"]
    if not isinstance(generation, str) or Path(generation).name != generation:
        raise ValueError("Invalid generation pointer")
    snapshot: dict[str, Any] = json.loads(
        (root / "generations" / generation / "snapshot.json").read_text()
    )
    if sha256(root / "generations" / generation / "snapshot.json") != pointer["sha256"]:
        raise ValueError("Published snapshot integrity check failed")
    return snapshot


def publish(
    raw_path: Path,
    model_path: Path = DEFAULT_MODEL,
    root: Path = DEFAULT_PUBLICATION,
    expected_symbols: list[str] | None = None,
) -> dict[str, Any]:
    from datetime import date

    model_path = resolve_model_path(model_path)

    raw = json.loads(raw_path.read_text())
    dates = {r["Snapshot_Date"] for r in raw}
    if len(dates) != 1:
        raise ValueError("Publication requires exactly one snapshot date")
    as_of = date.fromisoformat(dates.pop())
    observed = [r["Symbol"] for r in raw]
    if expected_symbols is not None and observed != expected_symbols:
        raise ValueError("Incomplete or changed universe; previous publication preserved")
    if (root / "latest.json").exists():
        previous = read_latest(root)
        if as_of.isoformat() < previous["snapshot_date"]:
            raise ValueError("Refusing to replace newer publication with older snapshot")
    rows, audit = clean_rows(raw, as_of)
    bundle = joblib.load(model_path)
    if bundle.get("sklearn_version") != __import__("sklearn").__version__:
        raise ValueError(
            "Installed sklearn differs from model; retrain or use training environment"
        )
    predictions = predict_rows(bundle, rows)
    records = []
    for row, prediction in zip(rows, predictions, strict=True):
        records.append(
            {
                **{k: row.get(k) for k in ["Symbol", "Company", "Sector"] + BASE_NUMERIC},
                **prediction,
                "Financial_Basis": row.get("Financial_Basis"),
                "Business_Type": row.get("Business_Type"),
                "Financial_Period": row.get("Annual_Financial_Period"),
                "Shareholding_Period": row.get("Shareholding_Period"),
                "Reason": "; ".join(
                    row["_quality_limits"]
                    + row["_assessment"]["reasons"]
                    + row["_assessment"]["limits"]
                ),
            }
        )
    snapshot = {
        "snapshot_date": as_of.isoformat(),
        "published_at": datetime.now(UTC).isoformat(),
        "policy_version": POLICY_VERSION,
        "model_sha256": sha256(model_path),
        "model_training_date": bundle["snapshot_date"],
        "classification_method": "Contextual rules; model prediction is advisory",
        "stock_count": len(records),
        "data_audit": audit,
        "stocks": records,
    }
    generation = as_of.isoformat() + "-" + uuid.uuid4().hex[:12]
    destination = root / "generations" / generation
    destination.mkdir(parents=True)
    atomic_json(destination / "snapshot.json", snapshot)
    fields = list(records[0])
    # Machine pipeline output, rather than a separately authored workbook.
    with (destination / "fundamentals.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    if any("http://" in str(v) or "https://" in str(v) for r in records for v in r.values()):
        raise ValueError("URL in published output")
    stored = json.loads((destination / "snapshot.json").read_text())
    if len(stored["stocks"]) != len(observed):
        raise ValueError("Incomplete generation")
    atomic_json(
        root / "latest.json",
        {"generation": generation, "sha256": sha256(destination / "snapshot.json")},
    )
    atomic_json(
        root / "status.json",
        {
            "status": "completed",
            "snapshot_date": as_of.isoformat(),
            "completed_at": snapshot["published_at"],
            "generation": generation,
        },
    )
    return snapshot
