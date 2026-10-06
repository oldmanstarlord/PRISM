"""Verify real score targets, reversible spacing, robust regression and fold-local selection."""

import joblib
import numpy as np
import pytest
from sklearn.base import clone, is_regressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import ParameterGrid

from backend.app.fundamentals.regression_improvement import (
    improved_regression_search,
    select_score_model,
)
from backend.app.fundamentals.score_estimators import (
    CatBoostScoreRegressor,
    TreeScoreRegressor,
    collapse_score_bands,
    spread_score_bands,
)
from backend.app.fundamentals.scores import score_codes


def test_score_spacing_is_monotone_and_reversible_including_boundaries():
    values = np.unique(np.r_[np.linspace(0, 100, 10001), [39.99, 59.99, 74.99, 89.99]])
    spaced = spread_score_bands(values)
    assert (np.diff(spaced) > 0).all()
    np.testing.assert_allclose(collapse_score_bands(spaced), values, rtol=0, atol=1e-10)
    np.testing.assert_array_equal(score_codes(collapse_score_bands(spaced)), score_codes(values))


def test_spacing_keeps_actual_numeric_information_within_each_band():
    values = np.array([61.23, 65.78, 74, 83.36, 89, 91.35, 99.97])
    spaced = spread_score_bands(values)
    assert len(np.unique(spaced)) == len(values)
    assert not np.isin(spaced, np.arange(5)).all()
    np.testing.assert_allclose(collapse_score_bands(spaced), values)


@pytest.mark.parametrize("scores", [[np.nan], [-1], [101]])
def test_invalid_score_targets_cannot_be_transformed(scores):
    with pytest.raises(ValueError, match="Target scores must be finite"):
        spread_score_bands(np.array(scores))


def test_transformed_tree_regression_predicts_actual_scores_and_serializes(tmp_path):
    x = np.arange(15).reshape(-1, 1)
    y = np.linspace(61.123, 73.789, 15)
    estimator = TransformedTargetRegressor(
        regressor=TreeScoreRegressor(ExtraTreesRegressor(n_estimators=25, random_state=1)),
        func=spread_score_bands,
        inverse_func=collapse_score_bands,
    )
    fitted = clone(estimator).fit(x, y)
    np.testing.assert_allclose(fitted.predict(x), y)
    assert is_regressor(fitted) and not hasattr(fitted, "classes_")
    joblib.dump(fitted, tmp_path / "score.joblib")
    np.testing.assert_array_equal(
        fitted.predict(x), joblib.load(tmp_path / "score.joblib").predict(x)
    )


def test_regression_model_selection_prioritizes_categories_and_breaks_ties_by_mae():
    results = {"mean_test_band_accuracy": [0.7, 0.8, 0.8], "mean_test_neg_mae": [-3, -6, -5]}
    assert select_score_model(results) == 2
    with pytest.raises(ValueError, match="Nonfinite inner-CV"):
        select_score_model({"mean_test_band_accuracy": [np.nan], "mean_test_neg_mae": [-3]})


def test_every_search_candidate_is_a_regressor_and_all_selection_is_in_pipeline():
    search = improved_regression_search(1, [(np.array([0, 1]), np.array([2]))])
    configurations = list(ParameterGrid(search.param_grid))
    assert len(configurations) == 112
    assert all(is_regressor(c["regressor"]) for c in configurations)
    assert list(search.estimator.named_steps) == [
        "features",
        "preprocess",
        "selection",
        "regressor",
    ]
    assert not hasattr(search.estimator.named_steps["selection"], "scores_")
    assert search.refit is select_score_model


def test_catboost_wrapper_is_regression_and_accepts_fractional_targets():
    x = np.arange(15, dtype=float).reshape(-1, 1)
    y = np.linspace(62.123, 89.456, 15)
    fitted = clone(CatBoostScoreRegressor(iterations=15)).fit(x, y)
    predictions = fitted.predict(x)
    assert is_regressor(fitted) and not hasattr(fitted, "classes_")
    assert predictions.shape == y.shape and np.isfinite(predictions).all()
    assert predictions.min() > 4  # These are scores, not label codes.
