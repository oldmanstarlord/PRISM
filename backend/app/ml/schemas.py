"""Schemas for ML Risk Model inference and AI Insights."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MLRequestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class MLHoldingInput(MLRequestModel):
    symbol: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9&.-]+$")
    weight: float = Field(gt=0.0, le=1.0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")
        return symbol


class MLPortfolioRequest(MLRequestModel):
    holdings: list[MLHoldingInput] = Field(min_length=1, max_length=200)


class MLHoldingSymbolsRequest(MLRequestModel):
    symbols: list[str] = Field(min_length=1, max_length=150)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        cleaned = [s.strip().upper() for s in value if s.strip()]
        if not cleaned:
            raise ValueError("At least one valid symbol is required")
        if any(len(symbol) > 40 for symbol in cleaned):
            raise ValueError("Symbols must be at most 40 characters")
        if any(not all(ch.isalnum() or ch in "&.-" for ch in symbol) for symbol in cleaned):
            raise ValueError("Symbols contain unsupported characters")
        return cleaned


class ModelStatusResponse(BaseModel):
    models: dict[str, Any]


class VolatilityForecastResponse(BaseModel):
    status: str
    portfolio_forecast: dict[str, Any] | None = None
    holdings_forecasts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class MarketRegimeResponse(BaseModel):
    status: str
    market_regime: dict[str, Any] | None = None
    error: str | None = None


class AnomalyDetectionResponse(BaseModel):
    status: str
    anomaly_analysis: dict[str, Any] | None = None
    error: str | None = None


class ScoreValidationResponse(BaseModel):
    status: str
    score_validation: dict[str, Any] | None = None
    error: str | None = None


class ComprehensiveInsightsResponse(BaseModel):
    model_statuses: dict[str, Any]
    volatility: dict[str, Any]
    regime: dict[str, Any]
    anomalies: dict[str, Any]
    score_validation: dict[str, Any]
    governance: dict[str, Any]
