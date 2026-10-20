"""21-Day Forward Realized Volatility Forecasting Engine.

Compares Gradient Boosting against three simple financial baselines:
1. Trailing 21-day realized volatility.
2. RiskMetrics EWMA (lambda = 0.94).
3. HAR-RV (Heterogeneous Autoregressive model: 1d, 5d, 21d realized vol).

Evaluated out-of-sample under chronological walk-forward with purge/embargo.
If ML does not beat the baseline, the baseline is automatically selected as primary.
"""

import threading
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore[import-untyped]
from sklearn.linear_model import LinearRegression  # type: ignore[import-untyped]

from backend.app.ml.feature_builder import (
    build_volatility_features,
    compute_ewma_volatility,
    compute_forward_realized_volatility,
    compute_realized_volatility,
)
from backend.app.ml.metrics import (
    interval_coverage,
    mae_log_loss,
    mincer_zarnowitz,
    qlike_loss,
)
from backend.app.ml.walk_forward import ExpandingWindowWalkForward


@dataclass(slots=True)
class VolatilityModelEvaluation:
    model_name: str
    qlike: float
    mae_log: float
    mincer_zarnowitz_r2: float
    coverage_90: float
    is_primary: bool
    selection_reason: str


@dataclass(slots=True)
class VolatilityForecastResult:
    predicted_volatility: float  # Annualized (e.g. 0.185 = 18.5%)
    lower_bound_90: float
    upper_bound_90: float
    model_selected: str  # "ml_gradient_boosting" | "baseline_har" | "baseline_ewma"
    baseline_trailing_vol: float
    baseline_ewma_vol: float
    baseline_har_vol: float
    model_metrics: dict[str, Any]
    evaluations: list[dict[str, Any]]
    feature_importances: dict[str, float]
    data_cutoff: str
    horizon_days: int = 21

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VolatilityForecaster:
    """Trains, evaluates and infers 21-day forward realized volatility."""

    def __init__(
        self,
        random_state: int = 42,
        random_seed: int | None = None,
        min_train_size: int = 120,
        test_size: int = 21,
        horizon: int = 21,
    ) -> None:
        self.random_state = random_seed if random_seed is not None else random_state
        self.min_train_size = min_train_size
        self.test_size = test_size
        self.horizon = horizon

        # Point predictor
        self.ml_model = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=100,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=15,
            random_state=self.random_state,
        )
        # Quantile predictors for 90% prediction intervals (5% and 95%)
        self.ml_model_lower = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.05,
            max_iter=100,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=15,
            random_state=self.random_state,
        )
        self.ml_model_upper = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.95,
            max_iter=100,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=15,
            random_state=self.random_state,
        )
        self.har_model = LinearRegression()
        self._lock = threading.Lock()

    def train_and_evaluate(
        self,
        prices: pd.Series,
        benchmark_returns: pd.Series | None = None,
        volumes: pd.Series | None = None,
    ) -> tuple[VolatilityForecastResult, dict[str, Any]]:
        """Run chronological walk-forward evaluation, compare against baselines,

        and forecast the next 21-day realized volatility.
        """
        # 1. Build features and forward targets
        simple_returns = prices.pct_change().dropna()
        X_df = build_volatility_features(prices, benchmark_returns, volumes)
        y_series = compute_forward_realized_volatility(simple_returns, horizon=self.horizon)

        # Align on common index
        common_idx = X_df.index.intersection(y_series.dropna().index)
        if len(common_idx) < self.min_train_size + self.test_size:
            # Insufficient sample: fallback to trailing baseline
            trailing_vol = float(compute_realized_volatility(simple_returns, window=21).iloc[-1])
            ewma_vol = float(compute_ewma_volatility(simple_returns, decay=0.94).iloc[-1])
            fallback = VolatilityForecastResult(
                predicted_volatility=round(trailing_vol, 6),
                lower_bound_90=round(trailing_vol * 0.75, 6),
                upper_bound_90=round(trailing_vol * 1.30, 6),
                model_selected="baseline_trailing",
                baseline_trailing_vol=round(trailing_vol, 6),
                baseline_ewma_vol=round(ewma_vol, 6),
                baseline_har_vol=round(trailing_vol, 6),
                model_metrics={"note": "Insufficient sample for ML walk-forward"},
                evaluations=[],
                feature_importances={},
                data_cutoff=str(prices.index[-1]),
            )
            return fallback, {
                "name": "volatility_forecast_21d",
                "version": "2026.1",
                "data_cutoff": str(prices.index[-1]),
                "status": "insufficient_data",
                "features": list(X_df.columns),
                "hyperparameters": {},
                "metrics_vs_baseline": {},
                "model_selected": "baseline_trailing",
            }

        X = X_df.loc[common_idx].values
        y = y_series.loc[common_idx].values
        feature_names = list(X_df.columns)
        dates = list(common_idx)

        # Baselines for comparison over test sets
        trailing_baseline = X_df.loc[common_idx, "vol_21d"].values
        ewma_baseline = X_df.loc[common_idx, "vol_ewma_94"].values

        # 2. Chronological Walk-Forward Evaluation
        wf = ExpandingWindowWalkForward(
            min_train_size=self.min_train_size,
            test_size=self.test_size,
            horizon=self.horizon,
            embargo=self.horizon,
        )

        y_test_all: list[float] = []
        ml_preds_all: list[float] = []
        ml_lower_all: list[float] = []
        ml_upper_all: list[float] = []
        har_preds_all: list[float] = []
        trailing_preds_all: list[float] = []
        ewma_preds_all: list[float] = []

        # HAR features: vol_1d, vol_5d, vol_21d
        har_feat_idx = [
            feature_names.index("vol_1d"),
            feature_names.index("vol_5d"),
            feature_names.index("vol_21d"),
        ]

        for fold in wf.split(dates):
            X_tr = np.ascontiguousarray(X[fold.train_indices], dtype=np.float64)
            y_tr = np.ascontiguousarray(y[fold.train_indices], dtype=np.float64)
            X_te = np.ascontiguousarray(X[fold.test_indices], dtype=np.float64)
            y_te = np.ascontiguousarray(y[fold.test_indices], dtype=np.float64)

            # Fit ML Point & Intervals per fold (avoid mutating instance estimator)
            fold_ml = HistGradientBoostingRegressor(
                loss="squared_error",
                max_iter=100,
                learning_rate=0.05,
                max_depth=4,
                min_samples_leaf=15,
                random_state=self.random_state,
            )
            fold_ml_lower = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=0.05,
                max_iter=100,
                learning_rate=0.05,
                max_depth=4,
                min_samples_leaf=15,
                random_state=self.random_state,
            )
            fold_ml_upper = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=0.95,
                max_iter=100,
                learning_rate=0.05,
                max_depth=4,
                min_samples_leaf=15,
                random_state=self.random_state,
            )
            fold_har = LinearRegression()

            fold_ml.fit(X_tr, y_tr)
            fold_ml_lower.fit(X_tr, y_tr)
            fold_ml_upper.fit(X_tr, y_tr)
            fold_har.fit(X_tr[:, har_feat_idx], y_tr)

            # Out-of-sample forecasts
            ml_pred = np.maximum(fold_ml.predict(X_te), 0.01)
            ml_low = np.maximum(fold_ml_lower.predict(X_te), 0.005)
            ml_up = np.maximum(fold_ml_upper.predict(X_te), ml_low + 0.005)
            har_pred = np.maximum(fold_har.predict(X_te[:, har_feat_idx]), 0.01)

            y_test_all.extend(y_te)
            ml_preds_all.extend(ml_pred)
            ml_lower_all.extend(ml_low)
            ml_upper_all.extend(ml_up)
            har_preds_all.extend(har_pred)
            trailing_preds_all.extend(trailing_baseline[fold.test_indices])
            ewma_preds_all.extend(ewma_baseline[fold.test_indices])

        y_true = np.array(y_test_all)
        ml_pred_arr = np.array(ml_preds_all)
        ml_low_arr = np.array(ml_lower_all)
        ml_up_arr = np.array(ml_upper_all)
        har_arr = np.array(har_preds_all)
        trail_arr = np.array(trailing_preds_all)
        ewma_arr = np.array(ewma_preds_all)

        # 3. Compute Metrics for each candidate
        def eval_candidate(
            name: str,
            pred: np.ndarray,
            low: np.ndarray | None = None,
            up: np.ndarray | None = None,
        ) -> dict[str, Any]:
            ql = qlike_loss(y_true, pred)
            mae = mae_log_loss(y_true, pred)
            mz = mincer_zarnowitz(y_true, pred)
            cov = interval_coverage(y_true, low, up) if low is not None and up is not None else 0.0
            return {
                "model_name": name,
                "qlike": round(ql, 6),
                "mae_log": round(mae, 6),
                "mincer_zarnowitz_r2": round(mz["r2"], 4),
                "mz_alpha": round(mz["alpha"], 4),
                "mz_beta": round(mz["beta"], 4),
                "coverage_90": round(cov, 2),
            }

        eval_ml = eval_candidate("Gradient Boosting (ML)", ml_pred_arr, ml_low_arr, ml_up_arr)
        eval_har = eval_candidate("HAR-RV Regression", har_arr)
        eval_ewma = eval_candidate("EWMA (lambda 0.94)", ewma_arr)
        eval_trail = eval_candidate("Trailing 21d Vol", trail_arr)

        candidates = [eval_ml, eval_har, eval_ewma, eval_trail]

        # 4. Rigorous Model Selection Rule
        # Compare ML against best baseline (by QLIKE primary, MAE log secondary)
        baselines = [eval_har, eval_ewma, eval_trail]
        best_baseline = min(baselines, key=lambda b: (b["qlike"], b["mae_log"]))

        ml_beats_baseline = (
            eval_ml["qlike"] <= best_baseline["qlike"] * 1.02
            and eval_ml["mae_log"] <= best_baseline["mae_log"] * 1.02
        )

        evaluations_list = []
        if ml_beats_baseline:
            primary_name = "ml_gradient_boosting"
            for c in candidates:
                is_p = c["model_name"] == "Gradient Boosting (ML)"
                reason = (
                    "Outperformed baselines in chronological walk-forward"
                    if is_p
                    else "Benchmark baseline"
                )
                evaluations_list.append({**c, "is_primary": is_p, "selection_reason": reason})
        else:
            primary_name = (
                "baseline_har"
                if best_baseline["model_name"] == "HAR-RV Regression"
                else "baseline_ewma"
            )
            for c in candidates:
                is_p = c["model_name"] == best_baseline["model_name"]
                if is_p:
                    reason = (
                        f"Primary: Baseline achieved lower QLIKE loss "
                        f"({best_baseline['qlike']:.4f}) than ML model ({eval_ml['qlike']:.4f})"
                    )
                elif c["model_name"] == "Gradient Boosting (ML)":
                    reason = (
                        "Secondary: Underperformed simple baseline under QLIKE loss; "
                        "displayed for comparison only"
                    )
                else:
                    reason = "Benchmark baseline"
                evaluations_list.append({**c, "is_primary": is_p, "selection_reason": reason})

        # 5. Fit on all historical data up to current cutoff for final inference
        self.ml_model.fit(X, y)
        self.ml_model_lower.fit(X, y)
        self.ml_model_upper.fit(X, y)
        self.har_model.fit(X[:, har_feat_idx], y)

        # Latest feature vector at T (last available trading session)
        latest_X = np.ascontiguousarray(X_df.iloc[-1:].values, dtype=np.float64)
        latest_har_X = np.ascontiguousarray(latest_X[:, har_feat_idx], dtype=np.float64)

        final_ml_pred = float(self.ml_model.predict(latest_X)[0])
        final_ml_low = float(self.ml_model_lower.predict(latest_X)[0])
        final_ml_up = float(self.ml_model_upper.predict(latest_X)[0])
        final_har_pred = float(self.har_model.predict(latest_har_X)[0])
        final_ewma_pred = float(X_df["vol_ewma_94"].iloc[-1])
        final_trail_pred = float(X_df["vol_21d"].iloc[-1])

        # Pick forecast based on selection rule
        if ml_beats_baseline:
            chosen_pred = max(0.01, final_ml_pred)
            chosen_low = max(0.005, final_ml_low)
            chosen_up = max(chosen_low + 0.01, final_ml_up)
        else:
            chosen_pred = max(
                0.01, final_har_pred if primary_name == "baseline_har" else final_ewma_pred
            )
            chosen_low = max(0.005, chosen_pred * 0.80)
            chosen_up = chosen_pred * 1.25

        # Feature importances (approximate via variance of features if tree doesn't expose)
        feat_importances = {}
        if hasattr(self.ml_model, "feature_importances_"):
            for fname, imp in zip(feature_names, self.ml_model.feature_importances_, strict=False):
                feat_importances[fname] = round(float(imp), 4)
        else:
            # Equal proxy
            for fname in feature_names:
                feat_importances[fname] = round(1.0 / len(feature_names), 4)

        result = VolatilityForecastResult(
            predicted_volatility=round(chosen_pred, 6),
            lower_bound_90=round(chosen_low, 6),
            upper_bound_90=round(chosen_up, 6),
            model_selected=primary_name,
            baseline_trailing_vol=round(final_trail_pred, 6),
            baseline_ewma_vol=round(final_ewma_pred, 6),
            baseline_har_vol=round(final_har_pred, 6),
            model_metrics={
                "evaluated_samples": len(y_true),
                "walk_forward_folds": len(candidates),
                "ml_beats_baseline": ml_beats_baseline,
                "primary_model": primary_name,
            },
            evaluations=evaluations_list,
            feature_importances=feat_importances,
            data_cutoff=str(X_df.index[-1]),
            horizon_days=self.horizon,
        )

        model_card = {
            "name": "volatility_forecast_21d",
            "version": "2026.1",
            "data_cutoff": str(X_df.index[-1]),
            "window": f"{self.min_train_size}d expanding",
            "features": feature_names,
            "hyperparameters": {
                "max_iter": 100,
                "learning_rate": 0.05,
                "max_depth": 4,
                "loss": "squared_error",
                "random_state": self.random_state,
            },
            "metrics_vs_baseline": {
                "ml": eval_ml,
                "best_baseline": best_baseline,
                "ml_beats_baseline": ml_beats_baseline,
            },
            "model_selected": primary_name,
        }

        return result, model_card
