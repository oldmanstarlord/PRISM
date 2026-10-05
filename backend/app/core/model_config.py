"""Pydantic schemas, validation, checksums, and loaders for versioned model_config."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ModelConfig


def canonical_json_hash(payload: dict[str, Any] | list[Any]) -> str:
    """Return a deterministic SHA-256 hex digest for canonical JSON."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class PortfolioRulesConfig(BaseModel):
    """Configuration for portfolio valuation, returns, and stale price rules."""

    input_modes: list[str] = Field(default_factory=lambda: ["quantity", "target_weight"])
    cash_symbol: str = "CASH"
    cash_currency: str = "INR"
    weight_normalization: str = "strict_sum_to_one"
    valuation_price: str = "adjusted_close"
    return_type: str = "log_return"
    annualisation_factor: int = 252
    default_lookback_days: int = 250
    rebalancing: str = "buy_and_hold"
    benchmark: str = "NIFTY 200"
    max_stale_days: int = 5
    risk_free_rate_source: str = "GOI_91D_TBILL"

    @field_validator("annualisation_factor")
    @classmethod
    def validate_annualisation(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("annualisation_factor must be positive")
        return v

    @field_validator("max_stale_days")
    @classmethod
    def validate_max_stale(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_stale_days must be at least 1")
        return v


class RiskScoreWeightsConfig(BaseModel):
    """Configuration for 8-dimension risk scoring weights and rules."""

    dimensions: dict[str, float] = Field(
        default_factory=lambda: {
            "market": 25.0,
            "fundamentals": 20.0,
            "liquidity": 10.0,
            "structure": 10.0,
            "relative": 10.0,
            "governance": 10.0,
            "events": 10.0,
            "macro": 5.0,
        }
    )
    default_component_weight: float = 1.0
    min_industry_group_size: int = 5
    min_coverage_ratio: float = 0.70
    tie_rule: str = "weak_percentile"

    @model_validator(mode="after")
    def validate_weights_sum_to_100(self) -> RiskScoreWeightsConfig:
        total = sum(self.dimensions.values())
        if abs(total - 100.0) > 1e-4:
            raise ValueError(f"Risk score dimension weights must sum to 100.0, got {total}")
        for dim, weight in self.dimensions.items():
            if weight < 0:
                raise ValueError(f"Dimension weight for '{dim}' cannot be negative, got {weight}")
        return self


class ConfidenceCapsConfig(BaseModel):
    stale_price_cap: float = 50.0
    stale_price_days: int = 5
    low_coverage_cap: float = 60.0
    low_coverage_threshold: float = 0.70


class ConfidenceFactorsConfig(BaseModel):
    """Configuration for confidence engine factors, weights, and hard caps."""

    factor_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "data_coverage": 1.0,
            "data_freshness": 1.0,
            "source_agreement": 1.0,
            "signal_agreement": 1.0,
            "model_stability": 1.0,
            "evidence_volume": 1.0,
        }
    )
    caps: ConfidenceCapsConfig = Field(default_factory=ConfidenceCapsConfig)
    max_age_days: dict[str, int] = Field(
        default_factory=lambda: {
            "market": 5,
            "liquidity": 5,
            "fundamentals": 120,
            "governance": 365,
            "events": 30,
            "macro": 30,
        }
    )

    @model_validator(mode="after")
    def validate_factors(self) -> ConfidenceFactorsConfig:
        if not self.factor_weights:
            raise ValueError("factor_weights cannot be empty")
        for factor, weight in self.factor_weights.items():
            if weight <= 0:
                raise ValueError(f"Factor weight for '{factor}' must be positive, got {weight}")
        return self


class ModelConfigEnvelope(BaseModel):
    """Envelope representation of a persisted model_config row."""

    id: UUID
    config_key: str
    version: str
    status: Literal["draft", "approved", "retired"]
    configuration: dict[str, Any]
    configuration_hash: str
    created_at: datetime
    approved_at: datetime | None = None
    approved_by: str | None = None

    def fingerprint(self) -> str:
        """Compute the unique fingerprint combining key, version, and configuration hash."""
        raw = f"{self.config_key}:{self.version}:{self.configuration_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_model_config(
    session: Session,
    config_key: str,
    version: str | None = None,
    approved_only: bool = False,
) -> ModelConfigEnvelope:
    """Load a model_config from the database.

    If version is None, loads the latest version by version string.
    If approved_only is True, raises ValueError if the config status is not 'approved'.
    """
    stmt = select(ModelConfig).where(ModelConfig.config_key == config_key)
    if version is not None:
        stmt = stmt.where(ModelConfig.version == version)
    else:
        stmt = stmt.order_by(ModelConfig.version.desc())

    if approved_only:
        stmt = stmt.where(ModelConfig.status == "approved")

    row = session.scalars(stmt).first()
    if row is None:
        mode_str = "approved " if approved_only else ""
        ver_str = f" version={version}" if version else ""
        raise ValueError(f"No {mode_str}model_config found for key='{config_key}'{ver_str}")

    if approved_only and row.status != "approved":
        raise ValueError(
            f"Config '{config_key}:{row.version}' has status '{row.status}', "
            "but approved_only is required"
        )

    return ModelConfigEnvelope(
        id=row.id,
        config_key=row.config_key,
        version=row.version,
        status=cast(Any, row.status),
        configuration=row.configuration,
        configuration_hash=row.configuration_hash,
        created_at=row.created_at,
        approved_at=row.approved_at,
        approved_by=row.approved_by,
    )
