"""Pydantic schemas for portfolio inputs, positions, risk metrics, and results."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HoldingInput(BaseModel):
    symbol: str
    quantity: float | None = None
    weight: float | None = None
    notes: str | None = None


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    owner_ref: str = "local-user"
    as_of: date | None = None
    holdings: list[HoldingInput] = Field(default_factory=list)
    source: str = "manual_entry"


class RowValidationError(BaseModel):
    row: int
    symbol: str | None = None
    field: str | None = None
    error: str


class PortfolioHoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    security_id: UUID | None = None
    symbol: str
    quantity: float | None = None
    weight: float
    as_of: date
    source: str
    notes: str | None = None


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    owner_ref: str
    created_at: datetime
    updated_at: datetime
    holdings: list[PortfolioHoldingOut] = Field(default_factory=list)


class PortfolioImportResult(BaseModel):
    portfolio: PortfolioOut | None = None
    errors: list[RowValidationError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RiskRunRequest(BaseModel):
    as_of: date | None = None
    config_version: str | None = None
    force_rerun: bool = False
    shrinkage_override: float | None = None


class RiskContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    security_id: UUID | None = None
    weight: float
    asset_volatility: float
    marginal_contribution: float
    percent_contribution: float
    beta: float | None = None
    notes: str | None = None


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float
    portfolio_return: float


class PortfolioRiskRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    as_of: date
    config_version: str
    config_fingerprint: str
    input_fingerprint: str
    window_size: int
    annualisation_factor: float
    portfolio_volatility: float
    portfolio_variance: float
    portfolio_beta: float | None = None
    max_drawdown: float
    var_historical_95: float | None = None
    var_parametric_95: float | None = None
    es_historical_95: float | None = None
    es_parametric_95: float | None = None
    shrinkage_intensity: float
    concentration_metrics: dict[str, Any] = Field(default_factory=dict)
    drawdown_series: list[DrawdownPoint] = Field(default_factory=list)
    contributions: list[RiskContributionOut] = Field(default_factory=list)
    status: str
    data_sufficiency: str
    envelope: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime


class DiversificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_risk_run_id: UUID
    enb_eigen: float
    enb_risk_entropy: float
    enb_default: float
    enb_default_type: str
    cluster_weights: dict[str, float]
    findings: dict[str, Any]
    config_fingerprint: str
    computed_at: datetime


class ShockRequest(BaseModel):
    symbol: str
    shock_pct: float
    method: str = "regression_beta"


class ShockResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    security_id: UUID | None = None
    weight: float
    estimated_impact_pct: float
    contribution_pct: float
    method_detail: dict[str, Any] = Field(default_factory=dict)


class ShockScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    shocked_security_id: UUID | None = None
    shocked_symbol: str
    shock_pct: float
    method_version: str
    portfolio_impact_pct: float
    banner: str
    assumptions: list[str]
    results: list[ShockResultOut]
    created_at: datetime
