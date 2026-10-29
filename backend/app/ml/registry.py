"""Auditable model-card and artifact storage with checksum validation."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

DEFAULT_MODELS_DIR = Path("data/models")
READY_STATUSES = {"ready", "baseline_selected"}


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(slots=True)
class ModelCard:
    name: str
    version: str
    type: str | None
    status: str
    data_cutoff: str | None
    training_start: str | None
    training_end: str | None
    validation_start: str | None
    validation_end: str | None
    test_start: str | None
    test_end: str | None
    features: list[str]
    feature_schema_version: str | None
    preprocessing: dict[str, Any]
    hyperparameters: dict[str, Any]
    random_seed: int | None
    baseline_definition: object | None
    metrics_vs_baseline: dict[str, Any]
    model_selected: str | None
    selection_reason: str | None
    methodology_version: str | None
    source_data_version: str | None
    artifact_path: str | None
    artifact_checksum: str | None
    library_versions: dict[str, str | None]
    configuration_hash: str
    trained_at: str
    failure_reason: str | None = None
    governance_notes: str = "Risk diagnostics only; no price-direction or trade signal."
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_config_fingerprint(
    model_name: str,
    version: str,
    features: list[str],
    hyperparameters: dict[str, Any],
) -> str:
    return _canonical_hash(
        {
            "model_name": model_name,
            "version": version,
            "features": features,
            "hyperparameters": hyperparameters,
        }
    )


class ModelRegistry:
    """Preserve versioned artifacts; failed attempts never replace the latest valid card."""

    def __init__(self, root_dir: Path | None = None, models_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or models_dir or DEFAULT_MODELS_DIR).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _card_path(self, name: str, version: str) -> Path:
        return self.root_dir / f"{name}_{version}_card.json"

    def save_artifact_and_card(self, artifact: object, metadata: dict[str, Any]) -> ModelCard:
        name = str(metadata["name"])
        version = str(metadata["version"])
        features = [str(value) for value in metadata.get("features", [])]
        hyperparameters = dict(metadata.get("hyperparameters", {}))
        configuration_hash = generate_config_fingerprint(
            name, version, features, hyperparameters
        )
        artifact_identity = _canonical_hash(
            {
                "configuration_hash": configuration_hash,
                "data_cutoff": metadata.get("data_cutoff"),
                "source_data_version": metadata.get("source_data_version"),
                "training_start": metadata.get("training_start"),
                "training_end": metadata.get("training_end"),
            }
        )
        artifact_name = f"{name}_{version}_{artifact_identity[:16]}.joblib"
        artifact_path = self.root_dir / artifact_name
        temporary = artifact_path.with_suffix(".joblib.tmp")
        joblib.dump(artifact, temporary)
        checksum = file_sha256(temporary)
        os.replace(temporary, artifact_path)
        card = self._make_card(
            metadata,
            configuration_hash=configuration_hash,
            artifact_path=artifact_name,
            artifact_checksum=checksum,
        )
        if card.status not in READY_STATUSES:
            raise ValueError("Usable artifacts require ready or baseline_selected status")
        self._write_card(card)
        latest = self.root_dir / f"{name}_card.json"
        temporary_latest = latest.with_suffix(".json.tmp")
        temporary_latest.write_text(
            json.dumps(card.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary_latest, latest)
        return card

    def save_failed_card(self, metadata: dict[str, Any]) -> ModelCard:
        status = str(metadata.get("status", "failed"))
        if status in READY_STATUSES:
            raise ValueError("Failure cards cannot have a ready status")
        name = str(metadata["name"])
        version = str(metadata["version"])
        features = [str(value) for value in metadata.get("features", [])]
        hyperparameters = dict(metadata.get("hyperparameters", {}))
        card = self._make_card(
            metadata,
            configuration_hash=generate_config_fingerprint(
                name, version, features, hyperparameters
            ),
            artifact_path=None,
            artifact_checksum=None,
        )
        self._write_card(card)
        return card

    def save_card(self, card: dict[str, Any] | ModelCard) -> ModelCard:
        """Persist metadata-only non-ready outcomes; ready outcomes require an artifact."""
        payload = card.to_dict() if isinstance(card, ModelCard) else dict(card)
        status = str(payload.get("status", "failed"))
        if status in READY_STATUSES:
            raise ValueError("Use save_artifact_and_card for a usable model")
        return self.save_failed_card(payload)

    def _make_card(
        self,
        metadata: dict[str, Any],
        *,
        configuration_hash: str,
        artifact_path: str | None,
        artifact_checksum: str | None,
    ) -> ModelCard:
        known = {
            "name",
            "version",
            "type",
            "status",
            "data_cutoff",
            "training_start",
            "training_end",
            "validation_start",
            "validation_end",
            "test_start",
            "test_end",
            "features",
            "feature_schema_version",
            "preprocessing",
            "hyperparameters",
            "random_seed",
            "baseline_definition",
            "metrics_vs_baseline",
            "model_selected",
            "selection_reason",
            "methodology_version",
            "source_data_version",
            "library_versions",
            "failure_reason",
            "governance_notes",
        }
        return ModelCard(
            name=str(metadata["name"]),
            version=str(metadata["version"]),
            type=metadata.get("type"),
            status=str(metadata.get("status", "failed")),
            data_cutoff=(
                str(metadata["data_cutoff"])
                if metadata.get("data_cutoff") is not None
                else None
            ),
            training_start=metadata.get("training_start"),
            training_end=metadata.get("training_end"),
            validation_start=metadata.get("validation_start"),
            validation_end=metadata.get("validation_end"),
            test_start=metadata.get("test_start"),
            test_end=metadata.get("test_end"),
            features=[str(item) for item in metadata.get("features", [])],
            feature_schema_version=metadata.get("feature_schema_version"),
            preprocessing=dict(metadata.get("preprocessing", {})),
            hyperparameters=dict(metadata.get("hyperparameters", {})),
            random_seed=metadata.get("random_seed"),
            baseline_definition=metadata.get("baseline_definition"),
            metrics_vs_baseline=dict(metadata.get("metrics_vs_baseline", {})),
            model_selected=metadata.get("model_selected"),
            selection_reason=metadata.get("selection_reason"),
            methodology_version=metadata.get("methodology_version"),
            source_data_version=metadata.get("source_data_version"),
            artifact_path=artifact_path,
            artifact_checksum=artifact_checksum,
            library_versions=dict(metadata.get("library_versions", {})),
            configuration_hash=configuration_hash,
            trained_at=datetime.now(UTC).isoformat(),
            failure_reason=metadata.get("failure_reason"),
            governance_notes=str(
                metadata.get(
                    "governance_notes",
                    "Risk diagnostics only; no price-direction or trade signal.",
                )
            ),
            extra={key: value for key, value in metadata.items() if key not in known},
        )

    def _write_card(self, card: ModelCard) -> None:
        path = self._card_path(card.name, card.version)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(card.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, path)

    def load_model_card(self, name: str) -> ModelCard | None:
        path = self.root_dir / f"{name}_card.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ModelCard(**data)

    def load_artifact(
        self, card: ModelCard, *, expected_feature_schema: str | None = None
    ) -> object:
        if card.status not in READY_STATUSES or not card.artifact_path:
            raise RuntimeError(f"Model {card.name} has no validated artifact")
        if expected_feature_schema and card.feature_schema_version != expected_feature_schema:
            raise ValueError(
                "Feature schema mismatch: "
                f"{card.feature_schema_version} != {expected_feature_schema}"
            )
        path = (self.root_dir / card.artifact_path).resolve()
        if path.parent != self.root_dir or not path.exists():
            raise FileNotFoundError(f"Artifact missing for {card.name}")
        actual = file_sha256(path)
        if actual != card.artifact_checksum:
            raise ValueError(f"Artifact checksum mismatch for {card.name}")
        return joblib.load(path)

    def get_all_model_statuses(self) -> dict[str, dict[str, Any]]:
        models = (
            ("volatility_forecast_21d", "21-Session Volatility Forecast"),
            ("market_regime_nifty50", "NIFTY 50 Market Regime"),
            ("anomaly_isolation_forest", "NIFTY 200 Anomaly Detection"),
            ("risk_score_calibration", "Five-Factor Score Validation"),
        )
        result: dict[str, dict[str, Any]] = {}
        for name, title in models:
            card = self.load_model_card(name)
            if card is None:
                result[name] = {
                    "model_name": title,
                    "model_version": None,
                    "status": "untrained",
                    "data_cutoff": None,
                    "trained_at": None,
                    "metrics_vs_baseline": {},
                    "failure_reason": "no_validated_model_card",
                }
            else:
                result[name] = {
                    "model_name": title,
                    "model_version": card.version,
                    "model_type": card.type,
                    "status": card.status,
                    "data_cutoff": card.data_cutoff,
                    "trained_at": card.trained_at,
                    "training_window": f"{card.training_start} to {card.training_end}",
                    "test_period": f"{card.test_start} to {card.test_end}",
                    "features_count": len(card.features),
                    "metrics_vs_baseline": card.metrics_vs_baseline,
                    "model_selected": card.model_selected,
                    "model_selected_rationale": card.selection_reason,
                    "configuration_fingerprint": card.configuration_hash,
                    "failure_reason": card.failure_reason,
                }
        return result
