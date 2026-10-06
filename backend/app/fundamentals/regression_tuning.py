"""Fixed broad parameter search; selection remains inside each outer training fold."""

from __future__ import annotations

import json
from typing import Any

from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, ParameterGrid, ParameterSampler
from sklearn.svm import SVR
from xgboost import XGBRegressor

from backend.app.fundamentals.regression import parameter_value
from backend.app.fundamentals.regression_improvement import improved_regression_search
from backend.app.fundamentals.score_estimators import (
    CatBoostScoreRegressor,
    TreeScoreRegressor,
    collapse_score_bands,
    spread_score_bands,
)
from backend.app.fundamentals.training import SEED

TREE_RANGES = {
    "estimator__n_estimators": [220, 400, 600],
    "estimator__max_features": [0.6, 0.8, 1.0],
    "estimator__max_depth": [None, 8, 12, 20],
    "estimator__min_samples_leaf": [1, 2, 3, 5],
    "estimator__min_samples_split": [2, 4, 8],
}


def configuration_definition(pipeline: Any, params: dict[str, Any]) -> dict[str, Any]:
    """Describe variable stages without memory addresses from callable column selectors."""
    estimator = clone(pipeline).set_params(**params)
    return {
        name: parameter_value(estimator.named_steps[name])
        for name in ("features", "selection", "regressor")
    }


def broad_regression_search(workers: int, cv: Any) -> GridSearchCV:
    """Exhaust 432 core tree combinations and sample fixed broader family ranges.

    Sampling uses a single predeclared seed, independently of data and validation results.
    Include the previous 112 candidates. Never search split seeds or label thresholds.
    """
    search = improved_regression_search(workers, cv)
    configurations = list(ParameterGrid(search.param_grid))
    extra = TreeScoreRegressor(ExtraTreesRegressor(n_jobs=1, random_state=SEED))
    core = {"regressor": [extra], "selection__k": ["all"]}
    core.update({"regressor__" + k: v for k, v in TREE_RANGES.items()})
    configurations.extend(ParameterGrid(core))
    tree_extras = {
        **TREE_RANGES,
        "estimator__criterion": ["squared_error", "absolute_error"],
        "estimator__bootstrap": [False, True],
        "estimator__ccp_alpha": [0.0, 0.01, 0.1],
        "estimator__max_leaf_nodes": [None, 15, 31, 63],
        "aggregation": ["mean", "median"],
    }
    families: list[tuple[Any, dict[str, Any], int]] = [
        (extra, tree_extras, 96),
        (
            TreeScoreRegressor(RandomForestRegressor(n_jobs=1, random_state=SEED)),
            tree_extras,
            48,
        ),
        (
            XGBRegressor(
                n_jobs=1, random_state=SEED, objective="reg:squarederror", tree_method="hist"
            ),
            {
                "n_estimators": [150, 300, 600],
                "learning_rate": [0.02, 0.05, 0.08, 0.15],
                "max_depth": [2, 3, 5, 7],
                "min_child_weight": [1, 3, 5],
                "subsample": [0.7, 1.0],
                "colsample_bytree": [0.6, 0.8, 1.0],
                "reg_alpha": [0.0, 0.1, 1.0],
                "reg_lambda": [1, 5, 20],
            },
            32,
        ),
        (
            HistGradientBoostingRegressor(random_state=SEED, early_stopping=False),
            {
                "max_iter": [150, 300, 600],
                "learning_rate": [0.02, 0.05, 0.1, 0.2],
                "max_leaf_nodes": [7, 15, 31],
                "min_samples_leaf": [3, 5, 10, 20],
                "l2_regularization": [0.1, 1, 5, 20],
            },
            24,
        ),
        (
            CatBoostScoreRegressor(),
            {
                "iterations": [150, 350, 600],
                "learning_rate": [0.03, 0.08, 0.15],
                "depth": [3, 5, 7],
                "l2": [1, 5, 15],
                "loss": ["RMSE", "MAE"],
            },
            24,
        ),
        (
            SVR(),
            {
                "C": [1, 10, 100, 1000],
                "epsilon": [0.01, 0.1, 1, 3],
                "gamma": ["scale", 0.001, 0.01, 0.1],
                "kernel": ["rbf", "linear"],
            },
            24,
        ),
        (Ridge(), {"alpha": [0.01, 0.1, 1, 10, 100, 1000]}, 8),
    ]
    for family_index, (model, tuning, count) in enumerate(families):
        sampling = {
            **tuning,
            "_transform": [False, True],
            "_selection": [30, 60, "all"],
            "_view": ["compact", "rich"],
        }
        for sampled in ParameterSampler(sampling, n_iter=count, random_state=SEED + family_index):
            transformed = sampled.pop("_transform")
            selection = sampled.pop("_selection")
            view = sampled.pop("_view")
            estimator = clone(model).set_params(**sampled)
            if isinstance(estimator, TreeScoreRegressor) and estimator.estimator.bootstrap:
                # Derive a predeclared sampling fraction from sampled settings, never from y.
                estimator.set_params(estimator__max_samples=0.8)
            if transformed:
                estimator = TransformedTargetRegressor(
                    regressor=estimator, func=spread_score_bands, inverse_func=collapse_score_bands
                )
            configurations.append(
                {
                    "regressor": estimator,
                    "selection__k": selection,
                    "features__view": view,
                }
            )
    # Compare complete constructor settings, so implicit defaults do not create duplicates.
    unique: dict[str, dict[str, Any]] = {}
    for params in configurations:
        key = json.dumps(configuration_definition(search.estimator, params), sort_keys=True)
        unique.setdefault(key, {k: [v] for k, v in params.items()})
    search.param_grid = list(unique.values())
    search.pre_dispatch = workers
    search.verbose = 1
    return search
