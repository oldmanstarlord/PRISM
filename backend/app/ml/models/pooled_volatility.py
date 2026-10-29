"""Pooled NIFTY 200 volatility model with chronological date partitions."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from backend.app.ml.feature_builder import (
    build_volatility_features,
    compute_forward_realized_volatility,
)
from backend.app.ml.metrics import interval_coverage, qlike_loss
from backend.app.ml.models.volatility_forecast import chronological_partitions


@dataclass(slots=True)
class PooledPrediction:
    value: float
    lower: float
    upper: float
    trailing: float
    model_selected: str


class PooledVolatilityForecaster:
    """Pooled candidate with one-hot stock identity and the same 21-session target."""

    def __init__(self, random_seed: int = 42, horizon: int = 21) -> None:
        self.random_seed = random_seed
        self.horizon = horizon
        self.symbols: list[str] = []
        self.feature_names: list[str] = []
        self.model = self._model()
        self.har = LinearRegression()
        self.selected_model: str | None = None
        self.interval_radius: float | None = None
        self.validation_qlike_by_symbol: dict[str, float] = {}

    def _model(self) -> HistGradientBoostingRegressor:
        return HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.05,
            max_depth=5,
            min_samples_leaf=30,
            random_state=self.random_seed,
        )

    def _panel(
        self,
        prices: pd.DataFrame,
        volumes: pd.DataFrame,
        benchmark_returns: pd.Series,
    ) -> pd.DataFrame:
        frames = []
        for symbol in self.symbols:
            feature = build_volatility_features(
                prices[symbol].dropna(), benchmark_returns, volumes[symbol].dropna()
            )
            returns = prices[symbol].dropna().pct_change(fill_method=None).dropna()
            target = compute_forward_realized_volatility(returns, self.horizon).rename("target")
            frame = feature.join(target, how="inner").dropna().assign(symbol=symbol)
            frames.append(frame)
        return pd.concat(frames).sort_index()

    def _matrix(self, panel: pd.DataFrame) -> np.ndarray:
        numeric = panel.loc[:, self.feature_names].to_numpy(dtype=float)
        identity = np.zeros((len(panel), len(self.symbols)), dtype=float)
        symbol_position = {symbol: index for index, symbol in enumerate(self.symbols)}
        for row_index, symbol in enumerate(panel["symbol"]):
            identity[row_index, symbol_position[str(symbol)]] = 1.0
        return np.hstack([numeric, identity])

    def fit(
        self,
        prices: pd.DataFrame,
        volumes: pd.DataFrame,
        benchmark_returns: pd.Series,
    ) -> dict[str, Any]:
        self.symbols = sorted(
            symbol
            for symbol in set(prices.columns) & set(volumes.columns)
            if not prices[symbol].dropna().empty and not volumes[symbol].dropna().empty
        )
        if len(self.symbols) < 2:
            raise ValueError("pooled_model_requires_at_least_two_symbols")
        sample_features = build_volatility_features(
            prices[self.symbols[0]].dropna(),
            benchmark_returns,
            volumes[self.symbols[0]].dropna(),
        )
        self.feature_names = list(sample_features.columns)
        panel = self._panel(prices, volumes, benchmark_returns)
        dates = sorted(set(panel.index))
        partitions = chronological_partitions(
            len(dates),
            min_train_size=252,
            validation_size=63,
            test_size=63,
            horizon=self.horizon,
        )
        if partitions is None:
            raise ValueError("insufficient_dates_for_pooled_purged_partitions")
        train_dates = {dates[index] for index in partitions.train}
        validation_dates = {dates[index] for index in partitions.validation}
        test_dates = {dates[index] for index in partitions.test}
        train = panel[panel.index.isin(train_dates)]
        validation = panel[panel.index.isin(validation_dates)]
        test = panel[panel.index.isin(test_dates)]
        x_train, x_validation, x_test = map(self._matrix, (train, validation, test))
        y_train = train["target"].to_numpy(dtype=float)
        y_validation = validation["target"].to_numpy(dtype=float)
        y_test = test["target"].to_numpy(dtype=float)
        har_indices = [self.feature_names.index(name) for name in ("vol_1d", "vol_5d", "vol_21d")]
        candidate = self._model()
        har = LinearRegression()
        candidate.fit(x_train, y_train)
        har.fit(x_train[:, har_indices], y_train)
        validation_predictions = {
            "pooled_gradient_boosting": np.maximum(candidate.predict(x_validation), 1e-8),
            "baseline_har": np.maximum(har.predict(x_validation[:, har_indices]), 1e-8),
            "baseline_ewma": validation["vol_ewma_94"].to_numpy(dtype=float),
            "baseline_trailing": validation["vol_21d"].to_numpy(dtype=float),
        }
        validation_metrics = {
            name: qlike_loss(y_validation, prediction)
            for name, prediction in validation_predictions.items()
        }
        best_baseline = min(
            ("baseline_har", "baseline_ewma", "baseline_trailing"),
            key=validation_metrics.__getitem__,
        )
        self.selected_model = (
            "pooled_gradient_boosting"
            if validation_metrics["pooled_gradient_boosting"]
            < validation_metrics[best_baseline]
            else best_baseline
        )
        chosen_validation = validation_predictions[self.selected_model]
        self.interval_radius = float(
            np.quantile(np.abs(y_validation - chosen_validation), 0.90, method="linear")
        )
        for symbol in self.symbols:
            mask = validation["symbol"].to_numpy() == symbol
            if np.any(mask):
                self.validation_qlike_by_symbol[symbol] = qlike_loss(
                    y_validation[mask], chosen_validation[mask]
                )
        combined = pd.concat([train, validation])
        x_combined = self._matrix(combined)
        self.model = self._model()
        self.har = LinearRegression()
        self.model.fit(x_combined, combined["target"].to_numpy(dtype=float))
        self.har.fit(
            x_combined[:, har_indices], combined["target"].to_numpy(dtype=float)
        )
        test_predictions = {
            "pooled_gradient_boosting": np.maximum(self.model.predict(x_test), 1e-8),
            "baseline_har": np.maximum(self.har.predict(x_test[:, har_indices]), 1e-8),
            "baseline_ewma": test["vol_ewma_94"].to_numpy(dtype=float),
            "baseline_trailing": test["vol_21d"].to_numpy(dtype=float),
        }
        test_metrics = {
            name: {
                "qlike": qlike_loss(y_test, prediction),
                "mae": float(np.mean(np.abs(y_test - prediction))),
                "rmse": float(np.sqrt(np.mean(np.square(y_test - prediction)))),
                "sample_count": len(y_test),
                "coverage_90": interval_coverage(
                    y_test,
                    np.maximum(prediction - self.interval_radius, np.finfo(float).eps),
                    prediction + self.interval_radius,
                ),
                "mean_interval_width": float(2.0 * self.interval_radius),
            }
            for name, prediction in test_predictions.items()
        }
        # Keep the train+validation fit used for the untouched test; test labels are never
        # fed back into weights, intervals, or selection.
        return {
            "status": "ready"
            if self.selected_model == "pooled_gradient_boosting"
            else "baseline_selected",
            "model_selected": self.selected_model,
            "validation": validation_metrics,
            "test": test_metrics,
            "training_start": str(dates[partitions.train[0]]),
            "training_end": str(dates[partitions.train[-1]]),
            "validation_start": str(dates[partitions.validation[0]]),
            "validation_end": str(dates[partitions.validation[-1]]),
            "test_start": str(dates[partitions.test[0]]),
            "test_end": str(dates[partitions.test[-1]]),
            "features": [*self.feature_names, "stock_identity_one_hot"],
        }

    def predict(
        self,
        symbol: str,
        prices: pd.Series,
        volumes: pd.Series,
        benchmark_returns: pd.Series,
    ) -> PooledPrediction:
        if self.selected_model is None or self.interval_radius is None:
            raise RuntimeError("Pooled volatility artifact is not fitted")
        features = build_volatility_features(prices, benchmark_returns, volumes)
        row = features.iloc[-1]
        panel = pd.DataFrame([row]).assign(symbol=symbol)
        matrix = self._matrix(panel)
        har_indices = [self.feature_names.index(name) for name in ("vol_1d", "vol_5d", "vol_21d")]
        values = {
            "pooled_gradient_boosting": float(max(self.model.predict(matrix)[0], 1e-8)),
            "baseline_har": float(max(self.har.predict(matrix[:, har_indices])[0], 1e-8)),
            "baseline_ewma": float(row["vol_ewma_94"]),
            "baseline_trailing": float(row["vol_21d"]),
        }
        value = values[self.selected_model]
        return PooledPrediction(
            value=value,
            lower=max(value - self.interval_radius, np.finfo(float).eps),
            upper=value + self.interval_radius,
            trailing=values["baseline_trailing"],
            model_selected=self.selected_model,
        )
