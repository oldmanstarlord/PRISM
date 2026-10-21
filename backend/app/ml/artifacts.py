"""Serializable ML artifact envelopes."""

from dataclasses import dataclass

from backend.app.ml.models.pooled_volatility import PooledVolatilityForecaster
from backend.app.ml.models.volatility_forecast import VolatilityForecaster


@dataclass(slots=True)
class VolatilityArtifactBundle:
    per_stock: dict[str, VolatilityForecaster]
    pooled: PooledVolatilityForecaster | None
    selection_by_symbol: dict[str, str]
    unavailable_reasons: dict[str, str]
