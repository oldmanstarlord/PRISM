"""Leakage-controlled 21-session realized-volatility forecasting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from backend.app.ml.feature_builder import (
    build_volatility_features,
    compute_forward_realized_volatility,
)
from backend.app.ml.metrics import interval_coverage, mincer_zarnowitz, qlike_loss

MODEL_NAME = "volatility_forecast_21d"
MODEL_VERSION = "2.0.0"
FEATURE_SCHEMA_VERSION = "volatility-features-v2"
METHODOLOGY_VERSION = "ml-risk-v2"


@dataclass(frozen=True, slots=True)
class ChronologicalPartitions:
    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray


def chronological_partitions(
    observations: int,
    *,
    min_train_size: int,
    validation_size: int,
    test_size: int,
    horizon: int,
) -> ChronologicalPartitions | None:
    """Create ordered train/validation/test sets with a horizon-sized purge at both boundaries."""
    test_start = observations - test_size
    validation_end = test_start - horizon
    validation_start = validation_end - validation_size
    train_end = validation_start - horizon
    if train_end < min_train_size or validation_start < 0:
        return None
    return ChronologicalPartitions(
        train=np.arange(0, train_end),
        validation=np.arange(validation_start, validation_end),
        test=np.arange(test_start, observations),
    )


@dataclass(slots=True)
class VolatilityForecastResult:
    predicted_volatility: float | None
    lower_bound_90: float | None
    upper_bound_90: float | None
    model_selected: str | None
    baseline_trailing_vol: float | None
    baseline_ewma_vol: float | None
    baseline_har_vol: float | None
    model_metrics: dict[str, Any]
    evaluations: list[dict[str, Any]]
    feature_importances: dict[str, float]
    data_cutoff: str
    horizon_days: int = 21
    status: str = "ready"
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _metrics(y_true: np.ndarray, prediction: np.ndarray) -> dict[str, float | int]:
    error = prediction - y_true
    mz = mincer_zarnowitz(y_true, prediction)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "qlike": qlike_loss(y_true, prediction),
        "sample_count": len(y_true),
        "mincer_zarnowitz_r2": mz["r2"],
        "mincer_zarnowitz_alpha": mz["alpha"],
        "mincer_zarnowitz_beta": mz["beta"],
    }


def _interval(
    point: np.ndarray, residual_radius: float
) -> tuple[np.ndarray, np.ndarray]:
    return np.maximum(point - residual_radius, np.finfo(float).eps), point + residual_radius


class VolatilityForecaster:
    """Train, validate, select, fit, and later infer without retraining."""

    def __init__(
        self,
        random_state: int = 42,
        random_seed: int | None = None,
        min_train_size: int = 80,
        test_size: int = 21,
        horizon: int = 21,
    ) -> None:
        self.random_state = random_seed if random_seed is not None else random_state
        self.min_train_size = min_train_size
        self.test_size = test_size
        self.horizon = horizon
        self.ml_model = self._new_ml_model()
        self.har_model = LinearRegression()
        self.feature_names: list[str] = []
        self.selected_model: str | None = None
        self.interval_radius: float | None = None

    def _new_ml_model(self) -> HistGradientBoostingRegressor:
        return HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=100,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=15,
            random_state=self.random_state,
        )

    def _unavailable(
        self, prices: pd.Series, feature_names: list[str], reason: str
    ) -> tuple[VolatilityForecastResult, dict[str, Any]]:
        cutoff = str(prices.index[-1]) if not prices.empty else "unknown"
        result = VolatilityForecastResult(
            predicted_volatility=None,
            lower_bound_90=None,
            upper_bound_90=None,
            model_selected=None,
            baseline_trailing_vol=None,
            baseline_ewma_vol=None,
            baseline_har_vol=None,
            model_metrics={},
            evaluations=[],
            feature_importances={},
            data_cutoff=cutoff,
            status="insufficient_data",
            failure_reason=reason,
        )
        return result, {
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "status": "insufficient_data",
            "data_cutoff": cutoff,
            "features": feature_names,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "failure_reason": reason,
        }

    def train_and_evaluate(
        self,
        prices: pd.Series,
        benchmark_returns: pd.Series | None = None,
        volumes: pd.Series | None = None,
    ) -> tuple[VolatilityForecastResult, dict[str, Any]]:
        prices = prices.dropna().sort_index()
        simple_returns = prices.pct_change(fill_method=None).dropna()
        features = build_volatility_features(prices, benchmark_returns, volumes)
        targets = compute_forward_realized_volatility(simple_returns, horizon=self.horizon)
        common = features.index.intersection(targets.dropna().index)
        feature_names = list(features.columns)
        partitions = chronological_partitions(
            len(common),
            min_train_size=self.min_train_size,
            validation_size=self.test_size,
            test_size=self.test_size,
            horizon=self.horizon,
        )
        if partitions is None:
            return self._unavailable(
                prices,
                feature_names,
                "insufficient_observations_for_purged_train_validation_test",
            )

        x = np.ascontiguousarray(features.loc[common].to_numpy(dtype=float))
        y = np.ascontiguousarray(targets.loc[common].to_numpy(dtype=float))
        trailing = features.loc[common, "vol_21d"].to_numpy(dtype=float)
        ewma = features.loc[common, "vol_ewma_94"].to_numpy(dtype=float)
        har_columns = [feature_names.index(name) for name in ("vol_1d", "vol_5d", "vol_21d")]

        candidate = self._new_ml_model()
        har = LinearRegression()
        candidate.fit(x[partitions.train], y[partitions.train])
        har.fit(x[partitions.train][:, har_columns], y[partitions.train])
        validation_predictions = {
            "ml_gradient_boosting": np.maximum(candidate.predict(x[partitions.validation]), 1e-8),
            "baseline_har": np.maximum(
                har.predict(x[partitions.validation][:, har_columns]), 1e-8
            ),
            "baseline_ewma": ewma[partitions.validation],
            "baseline_trailing": trailing[partitions.validation],
        }
        validation_metrics = {
            name: _metrics(y[partitions.validation], prediction)
            for name, prediction in validation_predictions.items()
        }
        best_baseline = min(
            ("baseline_har", "baseline_ewma", "baseline_trailing"),
            key=lambda name: validation_metrics[name]["qlike"],
        )
        candidate_wins = (
            validation_metrics["ml_gradient_boosting"]["qlike"]
            < validation_metrics[best_baseline]["qlike"]
        )
        selected = "ml_gradient_boosting" if candidate_wins else best_baseline
        selection_status = "ready" if candidate_wins else "baseline_selected"
        validation_residuals = np.abs(
            y[partitions.validation] - validation_predictions[selected]
        )
        residual_radius = float(np.quantile(validation_residuals, 0.90, method="linear"))

        fit_indices = np.concatenate([partitions.train, partitions.validation])
        self.ml_model = self._new_ml_model()
        self.har_model = LinearRegression()
        self.ml_model.fit(x[fit_indices], y[fit_indices])
        self.har_model.fit(x[fit_indices][:, har_columns], y[fit_indices])
        test_predictions = {
            "ml_gradient_boosting": np.maximum(self.ml_model.predict(x[partitions.test]), 1e-8),
            "baseline_har": np.maximum(
                self.har_model.predict(x[partitions.test][:, har_columns]), 1e-8
            ),
            "baseline_ewma": ewma[partitions.test],
            "baseline_trailing": trailing[partitions.test],
        }
        evaluations: list[dict[str, Any]] = []
        for name, prediction in test_predictions.items():
            values: dict[str, Any] = dict(_metrics(y[partitions.test], prediction))
            low, high = _interval(prediction, residual_radius)
            values.update(
                {
                    "model_name": name,
                    "coverage_90": interval_coverage(y[partitions.test], low, high),
                    "mean_interval_width": float(np.mean(high - low)),
                    "is_primary": name == selected,
                    "selection_metric": "validation_qlike_minimize",
                }
            )
            evaluations.append(values)

        # Preserve the train+validation fit used for the untouched test. Test outcomes never
        # enter fitted weights, thresholds, intervals, or model selection.
        self.feature_names = feature_names
        self.selected_model = selected
        self.interval_radius = residual_radius
        prediction = self.predict(prices, benchmark_returns, volumes)
        prediction.model_metrics = {
            "selection_status": selection_status,
            "selection_metric": "validation_qlike_minimize",
            "validation": validation_metrics,
            "test": next(item for item in evaluations if item["is_primary"]),
            "train_samples": len(partitions.train),
            "validation_samples": len(partitions.validation),
            "test_samples": len(partitions.test),
        }
        prediction.evaluations = evaluations
        prediction.status = selection_status

        dates = list(common)
        card = {
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "type": "supervised volatility regression",
            "status": selection_status,
            "data_cutoff": str(prices.index[-1]),
            "training_start": str(dates[partitions.train[0]]),
            "training_end": str(dates[partitions.train[-1]]),
            "validation_start": str(dates[partitions.validation[0]]),
            "validation_end": str(dates[partitions.validation[-1]]),
            "test_start": str(dates[partitions.test[0]]),
            "test_end": str(dates[partitions.test[-1]]),
            "purge_sessions": self.horizon,
            "embargo_sessions": self.horizon,
            "target": "sqrt(252 * mean(simple_return[t+1:t+21]^2))",
            "features": feature_names,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "preprocessing": {"imputation": None, "scaling": None},
            "hyperparameters": self.ml_model.get_params(),
            "random_seed": self.random_state,
            "baseline_definition": ["trailing_21d", "ewma_0.94", "har_1d_5d_21d"],
            "metrics_vs_baseline": {
                "validation": validation_metrics,
                "test": evaluations,
            },
            "model_selected": selected,
            "selection_reason": (
                "candidate_has_lower_validation_qlike"
                if candidate_wins
                else "baseline_has_lower_or_equal_validation_qlike"
            ),
            "methodology_version": METHODOLOGY_VERSION,
        }
        return prediction, card

    def predict(
        self,
        prices: pd.Series,
        benchmark_returns: pd.Series | None = None,
        volumes: pd.Series | None = None,
    ) -> VolatilityForecastResult:
        if self.selected_model is None or self.interval_radius is None:
            raise RuntimeError("Volatility artifact is not fitted")
        features = build_volatility_features(prices, benchmark_returns, volumes)
        missing = set(self.feature_names).difference(features.columns)
        if missing:
            raise ValueError(f"Feature schema mismatch; missing {sorted(missing)}")
        latest = np.ascontiguousarray(
            features.loc[:, self.feature_names].iloc[-1:].to_numpy(dtype=float)
        )
        har_columns = [self.feature_names.index(name) for name in ("vol_1d", "vol_5d", "vol_21d")]
        ml = float(max(self.ml_model.predict(latest)[0], 1e-8))
        har = float(max(self.har_model.predict(latest[:, har_columns])[0], 1e-8))
        ewma = float(features["vol_ewma_94"].iloc[-1])
        trailing = float(features["vol_21d"].iloc[-1])
        chosen = {
            "ml_gradient_boosting": ml,
            "baseline_har": har,
            "baseline_ewma": ewma,
            "baseline_trailing": trailing,
        }[self.selected_model]
        lower, upper = _interval(np.array([chosen]), self.interval_radius)
        return VolatilityForecastResult(
            predicted_volatility=chosen,
            lower_bound_90=float(lower[0]),
            upper_bound_90=float(upper[0]),
            model_selected=self.selected_model,
            baseline_trailing_vol=trailing,
            baseline_ewma_vol=ewma,
            baseline_har_vol=har,
            model_metrics={},
            evaluations=[],
            feature_importances={},
            data_cutoff=str(features.index[-1]),
            horizon_days=self.horizon,
        )
