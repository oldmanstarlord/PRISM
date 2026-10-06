"""Keep the score target while selecting regressors for accurate derived categories."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, ParameterGrid, StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.svm import SVR
from xgboost import XGBRegressor

from backend.app.fundamentals.data import LABEL_ENCODING, LIMITED, feature_frame, load_snapshot
from backend.app.fundamentals.estimators import FinancialInteractions
from backend.app.fundamentals.improvement import EVALUATION_SEED
from backend.app.fundamentals.regression import parameter_value, parameters, regression_search
from backend.app.fundamentals.score_estimators import (
    CatBoostScoreRegressor,
    TreeScoreRegressor,
    collapse_score_bands,
    spread_score_bands,
)
from backend.app.fundamentals.training import SEED


def select_score_model(results: dict[str, Any]) -> int:
    """Choose category accuracy in training CV; break exact ties by score error."""
    accuracy = np.asarray(results["mean_test_band_accuracy"])
    negative_error = np.asarray(results["mean_test_neg_mae"])
    if not np.isfinite(accuracy).all() or not np.isfinite(negative_error).all():
        raise ValueError("Nonfinite inner-CV measurements")
    return int(np.lexsort((-negative_error, -accuracy))[0])


def improved_regression_search(workers: int, cv: Any) -> GridSearchCV:
    original = regression_search(workers, cv)
    pipeline = Pipeline(
        [
            ("features", FinancialInteractions(view="compact")),
            ("preprocess", original.estimator.named_steps["preprocess"]),
            ("selection", SelectKBest(f_regression)),
            ("regressor", Ridge()),
        ]
    )
    families: list[tuple[Any, dict[str, Any]]] = [
        (
            TreeScoreRegressor(ExtraTreesRegressor(n_estimators=220, n_jobs=1, random_state=SEED)),
            {
                "estimator__max_features": [0.8, 1.0],
                "estimator__min_samples_leaf": [1, 3],
                "aggregation": ["mean", "median"],
            },
        ),
        (
            TreeScoreRegressor(
                RandomForestRegressor(n_estimators=220, n_jobs=1, random_state=SEED)
            ),
            {"estimator__max_features": [0.8, 1.0], "estimator__min_samples_leaf": [1, 3]},
        ),
        (
            HistGradientBoostingRegressor(max_iter=180, min_samples_leaf=3, random_state=SEED),
            {"max_leaf_nodes": [7, 15], "l2_regularization": [1, 5]},
        ),
        (
            XGBRegressor(
                n_estimators=180,
                learning_rate=0.08,
                n_jobs=1,
                random_state=SEED,
                objective="reg:squarederror",
                tree_method="hist",
            ),
            {"max_depth": [2, 3], "reg_lambda": [1, 5]},
        ),
        (CatBoostScoreRegressor(), {"depth": [3, 5], "loss": ["RMSE", "MAE"]}),
        (Ridge(), {"alpha": [1, 10]}),
        (SVR(epsilon=0.1), {"C": [10, 100]}),
    ]
    grids = []
    for model, tuning in families:
        for transformed in [False, True]:
            regressor = (
                TransformedTargetRegressor(
                    regressor=model, func=spread_score_bands, inverse_func=collapse_score_bands
                )
                if transformed
                else model
            )
            prefix = "regressor__regressor__" if transformed else "regressor__"
            grid = {prefix + k: v for k, v in tuning.items()}
            grid.update({"regressor": [regressor], "selection__k": [30, "all"]})
            grids.append(grid)
    return GridSearchCV(
        pipeline,
        grids,
        cv=cv,
        n_jobs=workers,
        scoring=original.scoring,
        refit=select_score_model,
        error_score="raise",
    )


def complete_search_metadata(
    output: Path,
    csv_path: Path,
    raw_path: Path,
    search_factory: Callable[[int, Any], GridSearchCV] = improved_regression_search,
) -> None:
    """Record nested base estimators, including reports made before family names were added."""
    report_path = output / "regression_report.json"
    report = json.loads(report_path.read_text())
    search = search_factory(2, [])
    grid = list(ParameterGrid(search.param_grid))
    if len(grid) != len(report["candidates"]):
        raise ValueError("Candidate grid changed; cannot complete report metadata")
    for i, (params, result) in enumerate(zip(grid, report["candidates"], strict=True)):
        result["candidate_index"] = i
        result["parameters"] = parameters(params)
        result["regressor_definition"] = parameter_value(
            clone(search.estimator).set_params(**params).named_steps["regressor"]
        )
    bundle = joblib.load(output / "model.joblib")
    final = bundle["pipeline"].named_steps["regressor"]
    family = parameters({"regressor": final})["regressor_family"]
    report["regressor_family"] = family
    report["final_parameters"]["regressor_family"] = family
    report["target_transform"] = getattr(getattr(final, "func", None), "__name__", "identity")
    # Embedded constructor settings may share the same displayed tuning keys. Reproduce
    # ambiguous inner fits to recover settings; held-out predictions remain unchanged.
    rows, _ = load_snapshot(csv_path, raw_path)
    eligible = [r for r in rows if r["Fundamental"] != LIMITED]
    frame = feature_frame(eligible, contextual=True, extended=True)
    y = np.array([r["Fundamental_Score"] for r in eligible], dtype=float)
    strata = np.array([LABEL_ENCODING[r["Fundamental"]] for r in eligible])
    symbol_index = {r["Symbol"]: i for i, r in enumerate(eligible)}
    splits = json.loads((output / "outer_splits.json").read_text())
    for fold, split in zip(report["folds"], splits, strict=True):
        selected = fold["selected_parameters"]
        if "regressor_definition" in fold:
            continue
        choices = []
        for params in grid:
            described = parameters(params)
            if "regressor_family" not in selected:
                described.pop("regressor_family")
            if described == selected:
                choices.append(params)
        if not choices:
            raise ValueError("Recorded fold parameters are absent from fixed search")
        if len(choices) > 1:
            train = [symbol_index[s] for s in split["training_symbols"]]
            inner = StratifiedKFold(
                n_splits=3, shuffle=True, random_state=EVALUATION_SEED + fold["fold"]
            )
            cv = list(inner.split(frame.iloc[train], strata[train]))
            accuracies = []
            negative_errors = []
            for params in choices:
                result = cross_validate(
                    clone(search.estimator).set_params(**params),
                    frame.iloc[train],
                    y[train],
                    cv=cv,
                    n_jobs=2,
                    scoring=search.scoring,
                    error_score="raise",
                )
                accuracies.append(float(np.mean(result["test_band_accuracy"])))
                negative_errors.append(float(np.mean(result["test_neg_mae"])))
            best = select_score_model(
                {"mean_test_band_accuracy": accuracies, "mean_test_neg_mae": negative_errors}
            )
            if not np.isclose(
                accuracies[best], fold["inner_selection_band_accuracy"], rtol=0, atol=1e-12
            ) or not np.isclose(
                -negative_errors[best], fold["inner_selection_mae_points"], rtol=0, atol=1e-12
            ):
                raise ValueError("Cannot reproduce the recorded inner selection measurements")
            choices = [choices[best]]
            fold["parameter_identity_reconstructed_using_training_cv"] = True
        fold["selected_parameters"] = parameters(choices[0])
        fold["regressor_definition"] = parameter_value(
            clone(search.estimator).set_params(**choices[0]).named_steps["regressor"]
        )
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False))
