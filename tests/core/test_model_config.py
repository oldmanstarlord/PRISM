"""Tests for model_config Pydantic schemas, validation, checksums, and fingerprinting (D1)."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from backend.app.core.model_config import (
    ConfidenceFactorsConfig,
    ModelConfigEnvelope,
    PortfolioRulesConfig,
    RiskScoreWeightsConfig,
    canonical_json_hash,
)


def test_portfolio_rules_validation() -> None:
    # Valid default config
    cfg = PortfolioRulesConfig()
    assert cfg.annualisation_factor == 252
    assert cfg.max_stale_days == 5

    # Negative annualisation factor fails validation
    with pytest.raises(ValidationError, match="annualisation_factor must be positive"):
        PortfolioRulesConfig(annualisation_factor=-1)

    # Invalid max_stale_days fails validation
    with pytest.raises(ValidationError, match="max_stale_days must be at least 1"):
        PortfolioRulesConfig(max_stale_days=0)


def test_risk_score_weights_validation() -> None:
    # Valid default sums to 100
    cfg = RiskScoreWeightsConfig()
    assert sum(cfg.dimensions.values()) == 100.0

    # Weights not summing to 100 fail
    with pytest.raises(ValidationError, match="weights must sum to 100.0"):
        RiskScoreWeightsConfig(
            dimensions={
                "market": 30.0,
                "fundamentals": 20.0,
                "liquidity": 10.0,
                "structure": 10.0,
                "relative": 10.0,
                "governance": 10.0,
                "events": 10.0,
                "macro": 5.0,  # Sum = 105.0
            }
        )

    # Negative weight fails
    with pytest.raises(ValidationError, match="cannot be negative"):
        RiskScoreWeightsConfig(
            dimensions={
                "market": 110.0,
                "fundamentals": -10.0,
            }
        )


def test_confidence_factors_validation() -> None:
    cfg = ConfidenceFactorsConfig()
    assert len(cfg.factor_weights) == 6
    assert cfg.caps.stale_price_cap == 50.0

    with pytest.raises(ValidationError, match="cannot be empty"):
        ConfidenceFactorsConfig(factor_weights={})

    with pytest.raises(ValidationError, match="must be positive"):
        ConfidenceFactorsConfig(factor_weights={"data_coverage": -0.5})


def test_canonical_json_hash_stability() -> None:
    d1 = {"b": 2, "a": 1, "c": [3, 2, 1]}
    d2 = {"a": 1, "c": [3, 2, 1], "b": 2}
    # Key order independent
    assert canonical_json_hash(d1) == canonical_json_hash(d2)


def test_config_envelope_fingerprint_changes_on_any_modification() -> None:
    from datetime import datetime
    from uuid import uuid4

    now = datetime.now(UTC)
    config_a = {"weight": 10}
    env1 = ModelConfigEnvelope(
        id=uuid4(),
        config_key="test_model",
        version="v1",
        status="draft",
        configuration=config_a,
        configuration_hash=canonical_json_hash(config_a),
        created_at=now,
    )
    fp1 = env1.fingerprint()

    # Change value -> hash changes -> fingerprint changes
    config_b = {"weight": 11}
    env2 = ModelConfigEnvelope(
        id=uuid4(),
        config_key="test_model",
        version="v1",
        status="draft",
        configuration=config_b,
        configuration_hash=canonical_json_hash(config_b),
        created_at=now,
    )
    assert env2.fingerprint() != fp1

    # Same config, different version -> fingerprint changes
    env3 = ModelConfigEnvelope(
        id=uuid4(),
        config_key="test_model",
        version="v2",
        status="draft",
        configuration=config_a,
        configuration_hash=canonical_json_hash(config_a),
        created_at=now,
    )
    assert env3.fingerprint() != fp1
