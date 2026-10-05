"""Check engineered financial relationships, ordinal probabilities and model evaluation."""

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from backend.app.fundamentals.estimators import (
    BalancedClassifier,
    FinancialInteractions,
    OrdinalClassifier,
    OrdinalRegressionClassifier,
    signed_log,
)
from backend.app.fundamentals.improvement import clustered_comparison, improvement_search


@pytest.fixture
def financial_frame():
    from backend.app.fundamentals.data import BASE_NUMERIC, EXTRA_NUMERIC, METRICS

    numeric = (
        BASE_NUMERIC
        + METRICS
        + EXTRA_NUMERIC
        + [
            "Annual_Revenue",
            "Annual_Core_EBIT",
            "Annual_Operating_Profit",
            "Annual_Duration_Months",
            "Annual_Aligned_CFO",
            "Borrowings",
        ]
    )
    frame = pd.DataFrame({k: [1.0, 1.0] for k in numeric})
    frame["Sector"] = ["Information Technology", "Power"]
    frame["Broad_Industry"] = ["IT - Software", "Power"]
    frame["Parent_Cash_Years"] = np.nan
    frame["Annual_Net_Profit"] = [10.0, 20.0]
    frame["Annual_Revenue"] = [100.0, 100.0]
    frame["Annual_Aligned_CFO"] = [15.0, -5.0]
    frame["Borrowings"] = [0.0, 50.0]
    frame["ROCE"] = [20.0, 10.0]
    frame["Debt_Equity"] = [0.5, 0.5]
    return frame


def test_financial_ratios_retain_negative_cash_and_zero_debt(financial_frame):
    result = FinancialInteractions().fit_transform(financial_frame)
    assert result.loc[0, "Net_Profit_Margin"] == 10
    assert pd.isna(result.loc[0, "CFO_to_Debt"])
    assert result.loc[0, "No_Borrowings"] == 1
    assert result.loc[1, "CFO_to_Debt"] == -0.1
    assert result.loc[1, "Current_Cash_to_Profit"] == -0.25


def test_same_debt_with_different_cash_and_returns_has_different_inputs(financial_frame):
    result = FinancialInteractions().fit_transform(financial_frame)
    assert result.loc[0, "Debt_Equity"] == result.loc[1, "Debt_Equity"]
    assert (
        result.loc[0, "Return_Adjusted_for_Leverage"]
        != result.loc[1, "Return_Adjusted_for_Leverage"]
    )
    assert result.loc[0, "Current_Cash_to_Profit"] != result.loc[1, "Current_Cash_to_Profit"]


def test_financial_transform_is_row_wise_and_does_not_mutate_input(financial_frame):
    before = financial_frame.copy()
    transform = FinancialInteractions().fit(financial_frame)
    batch = transform.transform(financial_frame)
    first = transform.transform(financial_frame.iloc[:1])
    pd.testing.assert_frame_equal(batch.iloc[:1], first)
    pd.testing.assert_frame_equal(financial_frame, before)


def test_parent_cash_is_used_without_filling_missing_parent_conversion(financial_frame):
    financial_frame.loc[0, "Parent_Cash_Years"] = 3
    financial_frame.loc[0, "Parent_Cash_Conversion"] = np.nan
    financial_frame.loc[0, "Parent_CFO"] = 25
    result = FinancialInteractions().fit_transform(financial_frame)
    assert result.loc[0, "Effective_CFO"] == 25
    assert pd.isna(result.loc[0, "Effective_Cash_Conversion"])


def test_compact_view_does_not_contain_scores_or_rule_grades(financial_frame):
    result = FinancialInteractions(view="compact").fit_transform(financial_frame)
    assert "FII_QoQ" not in result and "CFO_to_Debt" in result
    assert not any("Score" in c or "Assessment" in c for c in result.columns)


def test_signed_log_preserves_zero_negative_and_missing():
    result = signed_log(np.array([-10.0, 0, 10.0, np.nan]))
    assert result[0] < 0 and result[1] == 0 and result[2] > 0
    assert np.isnan(result[3])


def test_ordinal_estimator_is_cloneable_and_has_valid_probabilities(tmp_path):
    x = np.arange(40, dtype=float).reshape(-1, 1)
    y = np.repeat(np.arange(5), 8)
    estimator = OrdinalClassifier(LogisticRegression(C=10), balance=True)
    fitted = clone(estimator).fit(x, y)
    prob = fitted.predict_proba(x)
    assert prob.shape == (40, 5) and (prob >= 0).all()
    np.testing.assert_allclose(prob.sum(axis=1), 1)
    assert len(np.unique(fitted.predict(x))) == 5
    joblib.dump(fitted, tmp_path / "ordinal.joblib")
    np.testing.assert_array_equal(
        fitted.predict(x), joblib.load(tmp_path / "ordinal.joblib").predict(x)
    )


def test_ordinal_handles_constant_cumulative_boundaries():
    x = np.arange(12, dtype=float).reshape(-1, 1)
    y = np.repeat([1, 2, 3], 4)
    estimator = OrdinalClassifier(LogisticRegression()).fit(x, y)
    prob = estimator.predict_proba(x)
    np.testing.assert_allclose(prob[:, 0], 0)
    np.testing.assert_allclose(prob[:, 4], 0)
    np.testing.assert_allclose(prob.sum(axis=1), 1)


def test_balanced_wrapper_fits_only_received_labels():
    x = np.arange(20, dtype=float).reshape(-1, 1)
    y = np.repeat([0, 1], [17, 3])
    estimator = BalancedClassifier(HistGradientBoostingClassifier(min_samples_leaf=2, max_iter=5))
    fitted = clone(estimator).fit(x, y)
    assert fitted.classes_.tolist() == [0, 1]
    assert fitted.predict_proba(x).shape == (20, 2)


def test_search_keeps_feature_selection_inside_pipeline():
    from sklearn.model_selection import StratifiedKFold

    search = improvement_search(1, StratifiedKFold(n_splits=3))
    assert list(search.estimator.named_steps) == [
        "features",
        "preprocess",
        "selection",
        "classifier",
    ]
    assert not hasattr(search.estimator.named_steps["selection"], "scores_")


def test_bootstrap_pairs_stock_appearances():
    old = np.array([[True, False], [False, False], [True, True]])
    new = np.array([[True, True], [True, False], [True, True]])
    result = clustered_comparison(old, new)
    assert result["accuracy_gain"] == pytest.approx(1 / 3)
    assert result["paired_gain_bootstrap_95_interval"][0] >= 0


def test_ordinal_regression_predicts_fixed_labels_without_fake_probabilities():
    from sklearn.ensemble import ExtraTreesRegressor

    x = np.arange(40, dtype=float).reshape(-1, 1)
    y = np.repeat(np.arange(5), 8)
    estimator = OrdinalRegressionClassifier(ExtraTreesRegressor(n_estimators=10, random_state=1))
    fitted = clone(estimator).fit(x, y)
    np.testing.assert_array_equal(fitted.predict(x), y)
    assert not hasattr(fitted, "predict_proba")


def test_explicit_model_bypasses_active_pointer(tmp_path):
    from backend.app.fundamentals.publication import resolve_model_path

    explicit = tmp_path / "explicit.joblib"
    broken_pointer = tmp_path / "active.json"
    broken_pointer.write_text("INVALID JSON")
    assert resolve_model_path(explicit, broken_pointer) == explicit


def test_active_model_path_cannot_escape_models_directory(tmp_path):
    import json

    from backend.app.fundamentals.publication import DEFAULT_MODEL, resolve_model_path

    pointer = tmp_path / "active.json"
    pointer.write_text(json.dumps({"path": "../../escape.joblib", "sha256": "bad"}))
    with pytest.raises(ValueError, match="outside"):
        resolve_model_path(DEFAULT_MODEL, pointer)
