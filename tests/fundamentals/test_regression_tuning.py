"""Validate reproducible parameter coverage and preservation of numeric regression."""

import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone, is_regressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import make_scorer
from sklearn.model_selection import GridSearchCV, ParameterGrid, StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from backend.app.fundamentals import regression_improvement as metadata
from backend.app.fundamentals.improvement import EVALUATION_SEED
from backend.app.fundamentals.regression import band_accuracy, bounded_mae, parameters
from backend.app.fundamentals.regression_improvement import improved_regression_search
from backend.app.fundamentals.regression_tuning import (
    TREE_RANGES,
    broad_regression_search,
    configuration_definition,
)
from backend.app.fundamentals.score_estimators import CatBoostScoreRegressor, TreeScoreRegressor
from jobs.tune_fundamental_regression import write_search_plan


def definitions(search):
    return [
        json.dumps(configuration_definition(search.estimator, params), sort_keys=True)
        for params in ParameterGrid(search.param_grid)
    ]


def test_broad_search_is_deterministic_unique_and_preserves_previous_candidates():
    search = broad_regression_search(1, [])
    settings = definitions(search)
    assert settings == definitions(broad_regression_search(2, []))
    assert len(settings) == len(set(settings))
    assert len(settings) > 750
    assert set(definitions(improved_regression_search(1, []))) <= set(settings)
    assert all(is_regressor(p["regressor"]) for p in ParameterGrid(search.param_grid))


def test_every_proposed_core_tree_combination_is_present():
    search = broad_regression_search(1, [])
    required = {tuple(p[k] for k in TREE_RANGES) for p in ParameterGrid(TREE_RANGES)}
    available = set()
    for params in ParameterGrid(search.param_grid):
        estimator = clone(search.estimator).set_params(**params).named_steps["regressor"]
        if hasattr(estimator, "estimator"):
            settings = estimator.get_params()
            available.add(tuple(settings[k] for k in TREE_RANGES))
    assert len(required) == 432
    assert required <= available


def test_catboost_learning_rate_changes_numeric_score_fit():
    x = np.arange(20, dtype=float).reshape(-1, 1)
    y = np.linspace(62.123, 89.456, 20)
    slow = clone(CatBoostScoreRegressor(iterations=15, learning_rate=0.01)).fit(x, y)
    fast = clone(CatBoostScoreRegressor(iterations=15, learning_rate=0.3)).fit(x, y)
    assert is_regressor(slow) and is_regressor(fast)
    assert np.isfinite(fast.predict(x)).all()
    assert not np.allclose(slow.predict(x), fast.predict(x))


def test_completed_experiment_cannot_be_overwritten(tmp_path):
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"previous completed model")
    with pytest.raises(ValueError, match="cannot overwrite a completed experiment"):
        write_search_plan(tmp_path, tmp_path / "missing.csv", tmp_path / "missing.json")
    assert artifact.read_bytes() == b"previous completed model"
    assert not (tmp_path / "search_plan.json").exists()


def test_ambiguous_fold_constructor_recovery_uses_only_training_rows(tmp_path, monkeypatch):
    frame = pd.DataFrame({"x": np.arange(18, dtype=float)})
    y = 62 + 10 * np.sin(np.arange(18, dtype=float)) ** 2
    rows = [
        {"Symbol": f"S{i}", "Fundamental": "Moderate", "Fundamental_Score": float(score)}
        for i, score in enumerate(y)
    ]
    scoring = {
        "band_accuracy": make_scorer(band_accuracy),
        "neg_mae": make_scorer(bounded_mae, greater_is_better=False),
    }

    def factory(workers, cv):
        pipeline = Pipeline(
            [
                ("preprocess", FunctionTransformer(np.asarray)),
                ("regressor", TreeScoreRegressor(ExtraTreesRegressor(random_state=1))),
            ]
        )
        return GridSearchCV(
            pipeline,
            {
                "regressor": [
                    TreeScoreRegressor(ExtraTreesRegressor(n_estimators=n, random_state=1))
                    for n in [2, 12]
                ]
            },
            cv=cv,
            scoring=scoring,
            refit=metadata.select_score_model,
            n_jobs=workers,
        )

    inner = StratifiedKFold(n_splits=3, shuffle=True, random_state=EVALUATION_SEED + 1)
    splits = list(inner.split(frame.iloc[:12], np.zeros(12)))
    search = factory(1, splits).fit(frame.iloc[:12], y[:12])
    expected = search.best_estimator_.named_steps["regressor"].estimator.n_estimators
    report = {
        "candidates": [{}, {}],
        "final_parameters": {},
        "folds": [
            {
                "fold": 1,
                "selected_parameters": parameters(search.best_params_),
                "inner_selection_band_accuracy": float(
                    search.cv_results_["mean_test_band_accuracy"][search.best_index_]
                ),
                "inner_selection_mae_points": -float(
                    search.cv_results_["mean_test_neg_mae"][search.best_index_]
                ),
            }
        ],
    }
    (tmp_path / "regression_report.json").write_text(json.dumps(report))
    (tmp_path / "outer_splits.json").write_text(
        json.dumps([{"training_symbols": [r["Symbol"] for r in rows[:12]]}])
    )
    joblib.dump({"pipeline": search.best_estimator_}, tmp_path / "model.joblib")
    monkeypatch.setattr(metadata, "load_snapshot", lambda *args: (rows, {}))
    monkeypatch.setattr(metadata, "feature_frame", lambda *args, **kwargs: frame)
    seen = []

    def training_only(estimator, x, target, **kwargs):
        seen.append(list(x.index))
        return cross_validate(estimator, x, target, **kwargs)

    monkeypatch.setattr(metadata, "cross_validate", training_only)
    metadata.complete_search_metadata(tmp_path, tmp_path / "x.csv", tmp_path / "x.json", factory)
    recovered = json.loads((tmp_path / "regression_report.json").read_text())["folds"][0]
    assert (
        recovered["regressor_definition"]["parameters"]["estimator"]["parameters"]["n_estimators"]
        == expected
    )
    assert seen == [list(range(12)), list(range(12))]
