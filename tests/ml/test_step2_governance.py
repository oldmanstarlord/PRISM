"""Step 2 acceptance tests for leakage, missing data, and artifact governance."""

import ast
from pathlib import Path

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest

from backend.app.ml.feature_builder import build_volatility_features
from backend.app.ml.models.risk_score_validator import RiskScoreValidator
from backend.app.ml.models.volatility_forecast import chronological_partitions
from backend.app.ml.registry import ModelRegistry


def test_chronological_partitions_have_horizon_purge() -> None:
    partitions = chronological_partitions(
        500,
        min_train_size=252,
        validation_size=63,
        test_size=63,
        horizon=21,
    )
    assert partitions is not None
    assert partitions.train[-1] < partitions.validation[0] < partitions.test[0]
    assert partitions.validation[0] - partitions.train[-1] - 1 == 21
    assert partitions.test[0] - partitions.validation[-1] - 1 == 21


def test_missing_volume_does_not_create_constant_feature() -> None:
    rng = np.random.default_rng(8)
    dates = pd.date_range("2024-01-01", periods=180, freq="B")
    prices = pd.Series(
        100 * np.cumprod(1 + rng.normal(0, 0.01, len(dates))), index=dates
    )
    features = build_volatility_features(prices)
    assert "volume_spike_20d" not in features.columns


def test_insufficient_risk_history_has_null_statistics() -> None:
    dates = pd.date_range("2026-01-01", periods=40, freq="B")
    prices = pd.Series(np.linspace(100, 105, len(dates)), index=dates)
    result, card = RiskScoreValidator().validate_score(np.linspace(10, 90, 40), prices)
    assert result.status == "insufficient_data"
    assert result.spearman_ic_vol_21d is None
    assert result.worst_quintile_auc is None
    assert result.calibration_curve == []
    assert card["status"] == "insufficient_data"


def test_corrupted_artifact_is_rejected(tmp_path: Path) -> None:
    registry = ModelRegistry(models_dir=tmp_path)
    card = registry.save_artifact_and_card(
        {"fitted": True},
        {
            "name": "artifact_integrity_test",
            "version": "1.0.0-20261020",
            "type": "test estimator",
            "status": "ready",
            "data_cutoff": "2026-10-20",
            "training_start": "2025-01-01",
            "training_end": "2026-06-30",
            "features": ["observed_feature"],
            "feature_schema_version": "test-v1",
            "preprocessing": {"imputation": None},
            "hyperparameters": {},
            "metrics_vs_baseline": {},
        },
    )
    assert registry.load_artifact(card, expected_feature_schema="test-v1") == {
        "fitted": True
    }
    assert card.artifact_path is not None
    (tmp_path / card.artifact_path).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        registry.load_artifact(card, expected_feature_schema="test-v1")


def test_inference_module_has_no_training_import_or_fit_call() -> None:
    source = Path("jobs/run_ml_inference.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "jobs.train_models" not in imported_modules
    assert "fit" not in called_attributes
    assert "train_and_evaluate" not in called_attributes

