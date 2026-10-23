"""Versioned graph and model defaults."""

from dataclasses import asdict, dataclass

SCHEMA_VERSION = "prism-temporal-hetero-v1"
STOCK_FEATURES = ("return_5d", "volatility_20d", "volume_log_ratio_20d", "drawdown_60d")
INDUSTRY_FEATURES = ("median_return_5d", "median_volatility_20d", "dispersion_5d")
MARKET_FEATURES = ("median_return_5d", "median_volatility_20d", "dispersion_5d")


@dataclass(frozen=True)
class GraphConfig:
    lookback_days: int = 121
    min_return_observations: int = 100
    correlation_floor: float = 0.65
    max_correlation_neighbors: int = 3
    min_stocks: int = 20
    snapshot_step: int = 5
    train_fraction: float = 0.6
    validation_fraction: float = 0.2
    embargo_snapshots: int = 7
    sequence_length: int = 8

    def validate(self) -> None:
        if (
            self.lookback_days < max(self.min_return_observations + 1, 60)
            or self.min_return_observations < 2
            or self.min_stocks < 2
            or self.max_correlation_neighbors < 0
            or not -1 <= self.correlation_floor <= 1
        ):
            raise ValueError("Invalid graph coverage settings")
        if not 0 < self.train_fraction < 1 or not 0 < self.validation_fraction < 1:
            raise ValueError("Split fractions must be between zero and one")
        if self.train_fraction + self.validation_fraction >= 1:
            raise ValueError("Train and validation fractions leave no test period")
        if self.sequence_length < 2 or self.snapshot_step < 1 or self.embargo_snapshots < 0:
            raise ValueError("Invalid temporal settings")

    def manifest(self) -> dict[str, object]:
        self.validate()
        return asdict(self)
