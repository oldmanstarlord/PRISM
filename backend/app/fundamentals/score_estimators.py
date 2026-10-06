"""Continuous-score regression with robust aggregation and reversible target spacing."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.utils.validation import check_is_fitted

# Fixed published bands/precision, not anchors fitted to validation results.
SCORE_ANCHORS = np.array([0, 39.99, 40, 59.99, 60, 74.99, 75, 89.99, 90, 100])
SPACED_ANCHORS = np.array([0, 0.2, 1, 1.2, 2, 2.2, 3, 3.2, 4, 4.2])


def spread_score_bands(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if not np.isfinite(values).all() or ((values < 0) | (values > 100)).any():
        raise ValueError("Target scores must be finite and between 0 and 100")
    return cast(np.ndarray, np.interp(values, SCORE_ANCHORS, SPACED_ANCHORS))


def collapse_score_bands(spaced: np.ndarray) -> np.ndarray:
    values = np.asarray(spaced, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Transformed score predictions must be finite")
    return cast(np.ndarray, np.interp(values, SPACED_ANCHORS, SCORE_ANCHORS))


class TreeScoreRegressor(RegressorMixin, BaseEstimator):  # type: ignore[misc]
    """Fit trees to actual numeric scores; aggregate their numeric predictions robustly."""

    def __init__(self, estimator: Any, aggregation: str = "median") -> None:
        self.estimator = estimator
        self.aggregation = aggregation

    def fit(self, X: Any, y: Any) -> TreeScoreRegressor:
        values = np.asarray(y, dtype=float)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise ValueError("Tree regression requires finite continuous one-dimensional targets")
        if self.aggregation not in {"mean", "median"}:
            raise ValueError("Unknown numeric tree aggregation")
        self.estimator_ = clone(self.estimator).fit(X, values)
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X: Any) -> np.ndarray:
        check_is_fitted(self, "estimator_")
        if self.aggregation == "mean":
            return cast(np.ndarray, self.estimator_.predict(X))
        values = np.column_stack([tree.predict(X) for tree in self.estimator_.estimators_])
        return cast(np.ndarray, np.median(values, axis=1))


class CatBoostScoreRegressor(RegressorMixin, BaseEstimator):  # type: ignore[misc]
    """Sklearn-compatible scalar regressor; never creates or fits class targets."""

    def __init__(
        self,
        depth: int = 4,
        loss: str = "RMSE",
        l2: float = 5,
        iterations: int = 350,
        seed: int = 20261006,
        learning_rate: float = 0.08,
    ) -> None:
        self.depth = depth
        self.loss = loss
        self.l2 = l2
        self.iterations = iterations
        self.seed = seed
        self.learning_rate = learning_rate

    def fit(self, X: Any, y: Any) -> CatBoostScoreRegressor:
        from catboost import CatBoostRegressor

        values = np.asarray(y, dtype=float)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise ValueError("CatBoost requires finite continuous score targets")
        self.estimator_ = CatBoostRegressor(
            iterations=self.iterations,
            depth=self.depth,
            loss_function=self.loss,
            l2_leaf_reg=self.l2,
            learning_rate=self.learning_rate,
            boosting_type="Ordered",
            random_seed=self.seed,
            thread_count=1,
            verbose=False,
            allow_writing_files=False,
        ).fit(X, values)
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X: Any) -> np.ndarray:
        check_is_fitted(self, "estimator_")
        return cast(np.ndarray, self.estimator_.predict(X))
