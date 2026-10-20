"""Model Registry and Model Card Management.

Stores and loads model cards and artifacts in `data/models/`.
Generates configuration fingerprints and determines model freshness status:
- "trained": Model trained on data within threshold of current market cutoff.
- "stale": Model trained on older cutoff (> 30 days old).
- "untrained": No model artifact exists yet.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODELS_DIR = Path("data/models")


@dataclass(slots=True)
class ModelCard:
    name: str
    version: str
    data_cutoff: str
    window: str
    features: list[str]
    hyperparameters: dict[str, Any]
    metrics_vs_baseline: dict[str, Any]
    config_fingerprint: str
    trained_at: str
    status: str  # "trained" | "stale" | "untrained"
    model_selected: str  # "ml_model" | "baseline_model"
    governance_notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_config_fingerprint(
    model_name: str,
    version: str,
    features: list[str],
    hyperparameters: dict[str, Any],
) -> str:
    """Generate deterministic SHA-256 hash of model configuration."""
    payload = {
        "model_name": model_name,
        "version": version,
        "features": sorted(features),
        "hyperparameters": hyperparameters,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ModelRegistry:
    """Manages model card storage, retrieval, and readiness status."""

    def __init__(self, root_dir: Path | None = None, models_dir: Path | None = None) -> None:
        self.root_dir = root_dir or models_dir or DEFAULT_MODELS_DIR
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_card(self, card: dict[str, Any] | ModelCard) -> ModelCard:
        """Convenience method to save a card from a dictionary or ModelCard instance."""
        if isinstance(card, ModelCard):
            card_path = self.root_dir / f"{card.name}_card.json"
            try:
                with open(card_path, "w", encoding="utf-8") as f:
                    json.dump(card.to_dict(), f, indent=2)
            except Exception as exc:
                logger.warning(
                    "Failed to save model card to %s: %s", card_path, type(exc).__name__
                )
            return card

        return self.save_model_card(
            name=str(card.get("name", "unnamed_model")),
            version=str(card.get("version", "2026.1")),
            data_cutoff=str(card.get("data_cutoff", "unknown")),
            window=str(card.get("window", "expanding")),
            features=list(card.get("features", [])),
            hyperparameters=dict(card.get("hyperparameters", {})),
            metrics_vs_baseline=dict(card.get("metrics_vs_baseline", card.get("metrics", {}))),
            model_selected=str(card.get("model_selected", "ml_model")),
            governance_notes=str(
                card.get(
                    "governance_notes",
                    "Model estimate of risk; no price direction or trade signals.",
                )
            ),
        )

    def save_model_card(
        self,
        name: str,
        version: str,
        data_cutoff: str,
        window: str,
        features: list[str],
        hyperparameters: dict[str, Any],
        metrics_vs_baseline: dict[str, Any],
        model_selected: str = "ml_model",
        governance_notes: str = "Model estimate of risk; no price direction or trade signals.",
    ) -> ModelCard:
        """Serialize and persist model card to disk."""
        fingerprint = generate_config_fingerprint(name, version, features, hyperparameters)
        now_str = datetime.now(UTC).isoformat()

        card = ModelCard(
            name=name,
            version=version,
            data_cutoff=data_cutoff,
            window=window,
            features=features,
            hyperparameters=hyperparameters,
            metrics_vs_baseline=metrics_vs_baseline,
            config_fingerprint=fingerprint,
            trained_at=now_str,
            status="trained",
            model_selected=model_selected,
            governance_notes=governance_notes,
        )

        card_path = self.root_dir / f"{name}_card.json"
        try:
            with open(card_path, "w", encoding="utf-8") as f:
                json.dump(card.to_dict(), f, indent=2)
        except Exception as exc:
            logger.warning("Failed to save model card to %s: %s", card_path, type(exc).__name__)

        return card

    def load_model_card(self, name: str) -> ModelCard | None:
        """Load model card from disk if present."""
        card_path = self.root_dir / f"{name}_card.json"
        if not card_path.exists():
            return None

        try:
            with open(card_path, encoding="utf-8") as f:
                data = json.load(f)
            return ModelCard(**data)
        except Exception as exc:
            logger.warning("Failed to load model card from %s: %s", card_path, type(exc).__name__)
            return None

    def get_all_model_statuses(self) -> dict[str, dict[str, Any]]:
        """Return status dictionary across all 4 PRISM ML models."""
        expected_models = [
            ("volatility_forecast_21d", "21-Day Forward Realized Volatility"),
            ("market_regime_nifty50", "NIFTY 50 Markov Regime Detection"),
            ("anomaly_isolation_forest", "Cross-Sectional Anomaly Detection"),
            ("risk_score_calibration", "5-Factor Risk Score Calibration"),
        ]

        result: dict[str, dict[str, Any]] = {}
        for m_id, title in expected_models:
            card = self.load_model_card(m_id)
            if card is not None:
                result[m_id] = {
                    "id": m_id,
                    "title": title,
                    "version": card.version,
                    "status": card.status,
                    "data_cutoff": card.data_cutoff,
                    "trained_at": card.trained_at,
                    "model_selected": card.model_selected,
                    "metrics": card.metrics_vs_baseline,
                    "config_fingerprint": card.config_fingerprint,
                }
            else:
                result[m_id] = {
                    "id": m_id,
                    "title": title,
                    "version": "2026.1",
                    "status": "untrained",
                    "data_cutoff": None,
                    "trained_at": None,
                    "model_selected": "baseline_model",
                    "metrics": {"note": "Model not trained yet; run jobs/train_models.py"},
                    "config_fingerprint": "none",
                }
        return result
