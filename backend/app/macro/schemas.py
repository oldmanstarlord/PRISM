"""Pydantic schemas for macroeconomic API endpoints (D3, D5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class MacroSeriesDefinitionOut(BaseModel):
    series_key: str
    name: str
    source: str
    frequency: str
    unit: str
    license_note: str
    is_active: bool


class MacroObservationOut(BaseModel):
    obs_date: date
    value: float
    published_at: datetime
    source: str | None = None
    version: int


class MacroSeriesDetailOut(BaseModel):
    series: MacroSeriesDefinitionOut
    observations: list[MacroObservationOut]
    total_observations: int
    latest_observation: MacroObservationOut | None = None


class MarketRegimeOut(BaseModel):
    as_of: date
    regime: str  # "calm" | "trending" | "stressed"
    features: dict[str, Any]
    config_version: str
    computed_at: datetime | None = None


class SectorMacroSensitivityOut(BaseModel):
    industry: str
    series_key: str
    series_name: str | None = None
    window_end: date
    beta: float
    t_stat: float
    n_obs: int
    p_value: float
    is_significant: bool
    config_version: str


class StockMacroExposureOut(BaseModel):
    symbol: str
    industry: str
    regime: str
    regime_multiplier: float
    macro_score: float | None = None
    sensitivities: list[SectorMacroSensitivityOut]
    recent_shocks: dict[str, Any]
    limitations: list[str] = Field(default_factory=list)
