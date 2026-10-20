"""Versioned request and response contracts for session-only portfolio analytics."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PortfolioHoldingInput(BaseModel):
    symbol: str
    weight: float = Field(gt=0.0, le=1.0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        return symbol


class StressScenarioInput(BaseModel):
    kind: Literal["stock", "industry", "market", "correlation"]
    target: str = ""
    shock_percent: float = Field(ge=-50.0, le=100.0)

    @field_validator("target")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        target = value.strip()
        return target

    @field_validator("shock_percent")
    @classmethod
    def reject_zero_shock(cls, value: float) -> float:
        if abs(value) < 1e-12:
            raise ValueError("shock_percent must be non-zero")
        return value


class PortfolioAnalysisRequest(BaseModel):
    holdings: list[PortfolioHoldingInput] = Field(min_length=1, max_length=200)
    window: int = Field(default=250, ge=60, le=750)
    stress: StressScenarioInput | None = None


class AnalysisEnvelope(BaseModel):
    as_of: date
    lookback_start: date
    data_cutoff: datetime
    requested_observations: int
    observations_used: int
    return_frequency: str
    annualisation_factor: int
    weighting_assumption: str
    missing_data_rule: str
    implementation_version: str


class PerformancePoint(BaseModel):
    trade_date: date
    portfolio_index: float
    drawdown: float


class PerformanceSummary(BaseModel):
    total_return: float
    annualized_return: float
    annualized_volatility: float
    downside_volatility: float
    max_drawdown: float
    points: list[PerformancePoint]


class HoldingAnalytics(BaseModel):
    symbol: str
    industry: str
    weight: float
    annualized_volatility: float
    marginal_risk: float
    risk_contribution: float
    divergence_20d: float | None
    divergence_band: str | None


class IndustryWeight(BaseModel):
    industry: str
    weight: float


class ConcentrationSummary(BaseModel):
    holding_hhi: float
    effective_holdings: float
    largest_holding_symbol: str
    largest_holding_weight: float
    industry_hhi: float
    effective_industries: float
    industry_weights: list[IndustryWeight]


class DiversificationSummary(BaseModel):
    effective_bets_risk: float
    effective_bets_correlation: float
    interpretation: str


class MstEdgeSummary(BaseModel):
    symbol_a: str
    symbol_b: str
    correlation: float
    distance: float
    persistence: float | None
    confidence: Literal["unavailable", "low", "moderate", "high"]


class MstPathSummary(BaseModel):
    symbol_a: str
    symbol_b: str
    hops: int
    average_correlation: float
    weakest_correlation: float
    positive_path_product: float
    path: list[str]
    minimum_edge_persistence: float | None
    confidence: Literal["unavailable", "low", "moderate", "high"]


class MstBridgeSummary(BaseModel):
    symbol: str
    path_pair_count: int
    is_holding: bool


class MstClusterSummary(BaseModel):
    cluster_id: str
    weight: float
    holding_symbols: list[str]
    full_node_count: int


class MstStabilitySummary(BaseModel):
    method: str
    runs_compared: int
    window_ends: list[date]
    consecutive_edge_overlap: float | None
    current_edge_persistence: float | None
    confidence: Literal["unavailable", "low", "moderate", "high"]
    reason: str


class MstPortfolioSummary(BaseModel):
    run_id: str
    as_of: date
    cluster_correlation_floor: float
    direct_edges: list[MstEdgeSummary]
    subtree_edges: list[MstEdgeSummary]
    holding_paths: list[MstPathSummary]
    bridge_stocks: list[MstBridgeSummary]
    clusters: list[MstClusterSummary]
    cluster_hhi: float
    effective_clusters: float
    stability: MstStabilitySummary


class StressHoldingResult(BaseModel):
    symbol: str
    sensitivity: float
    estimated_return_percent: float
    portfolio_contribution_percent: float


class StressScenarioResult(BaseModel):
    kind: Literal["stock", "industry", "market", "correlation"]
    target: str
    shock_percent: float
    method: str
    portfolio_impact_percent: float
    results: list[StressHoldingResult]
    assumptions: list[str]
    disclaimer: str


class PortfolioAnalysisResponse(BaseModel):
    envelope: AnalysisEnvelope
    performance: PerformanceSummary
    holdings: list[HoldingAnalytics]
    concentration: ConcentrationSummary
    diversification: DiversificationSummary
    mst: MstPortfolioSummary
    stress: StressScenarioResult | None
    findings: list[str]
    limitations: list[str]
