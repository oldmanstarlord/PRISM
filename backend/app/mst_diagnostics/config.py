"""Configuration loader for MST diagnostics."""

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ModelConfig

DEFAULT_MST_DIAGNOSTICS_CONFIG: dict[str, Any] = {
    "history_windows_count": 26,
    "cluster_rule": "remove_k_longest_edges",
    "cluster_rule_version": "longest-k-edges-v1",
    "cluster_k_cut": 10,
    "stability_thresholds": {
        "high": 0.65,
        "medium": 0.45,
    },
    "default_variant": "raw",
}


@dataclass(frozen=True, slots=True)
class MstDiagnosticsConfig:
    history_windows_count: int
    cluster_rule: str
    cluster_rule_version: str
    cluster_k_cut: int
    threshold_high: float
    threshold_medium: float
    default_variant: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MstDiagnosticsConfig":
        thresholds = data.get("stability_thresholds", {})
        return cls(
            history_windows_count=int(data.get("history_windows_count", 26)),
            cluster_rule=str(data.get("cluster_rule", "remove_k_longest_edges")),
            cluster_rule_version=str(data.get("cluster_rule_version", "longest-k-edges-v1")),
            cluster_k_cut=int(data.get("cluster_k_cut", 10)),
            threshold_high=float(thresholds.get("high", 0.65)),
            threshold_medium=float(thresholds.get("medium", 0.45)),
            default_variant=str(data.get("default_variant", "raw")),
        )


def load_mst_diagnostics_config(session: Session | None = None) -> MstDiagnosticsConfig:
    """Load approved mst_diagnostics config from model_config or fallback to approved defaults."""
    if session is not None:
        try:
            row = session.scalar(
                select(ModelConfig)
                .where(
                    ModelConfig.config_key == "mst_diagnostics", ModelConfig.status == "approved"
                )
                .order_by(ModelConfig.created_at.desc())
                .limit(1)
            )
            if row is not None:
                cfg = row.configuration
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                if isinstance(cfg, dict):
                    return MstDiagnosticsConfig.from_dict(cfg)
        except Exception:
            # Fallback to approved defaults if table not accessible
            pass

    return MstDiagnosticsConfig.from_dict(DEFAULT_MST_DIAGNOSTICS_CONFIG)
