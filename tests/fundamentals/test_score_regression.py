"""Check continuous targets, fixed bands, missing-data gates and published score consistency."""

import json
from datetime import date

import joblib
import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import ParameterGrid
from sklearn.pipeline import Pipeline

from backend.app.fundamentals.data import (
    BASE_NUMERIC,
    LIMITED,
    POLICY_VERSION,
    SCHEMA_VERSION,
    clean_rows,
    feature_frame,
)
from backend.app.fundamentals.publication import publish, read_latest
from backend.app.fundamentals.regression import (
    activate_regression,
    regression_measurements,
    regression_search,
    train_regression,
)
from backend.app.fundamentals.scores import bounded_scores, score_codes
from backend.app.fundamentals.training import predict_rows, preprocessing


@pytest.fixture
def score_observation():
    history = {"annual": {}, "quarters": {}, "balance": {}, "cash": {}, "returns": {}}
    for year in range(2023, 2027):
        p = f"{year}-03-31"
        factor = 1.1 ** (year - 2023)
        history["annual"][p] = {
            "months": 12,
            "revenue": 1000 * factor,
            "operating": 200 * factor,
            "net": 100 * factor,
            "interest": 10 * factor,
            "ebit": 180 * factor,
            "margin": 20,
            "payout": 30,
        }
        history["balance"][p] = {"debt": 100, "equity": 200, "de": 0.5}
        history["cash"][p] = 110 * factor
        history["returns"][p] = 20
    for year, factor in [(2025, 1), (2026, 1.1)]:
        history["quarters"][f"{year}-06-30"] = {
            "revenue": 250 * factor,
            "net": 25 * factor,
            "ebit": 45 * factor,
        }
    row = dict.fromkeys(BASE_NUMERIC, 0)
    row.update(
        Symbol="TEST",
        Company="Test Ltd",
        Sector="Information Technology",
        Broad_Industry="IT - Software",
        Business_Type="Non_Financial_or_Capital_Markets",
        Snapshot_Date="2026-10-05",
        Balance_Sheet_Period="2026-03-31",
        Annual_Financial_Period="2026-03-31",
        ROCE_Period="2026-03-31",
        Shareholding_Period="2026-06-30",
        Market_Cap=1000,
        PE=20,
        Debt_Equity=0.5,
        OPM=20,
        ROCE=20,
        _equity=200,
        _net_profit=130,
        _last_annual_profit=130,
        _financial_history=history,
        Promoter_Encumbrance=0,
        Encumbrance_Total_Capital=0,
    )
    return row


@pytest.fixture
def score_bundle(score_observation):
    rows, _ = clean_rows([score_observation], date(2026, 10, 5))
    frame = feature_frame(rows, extended=True)
    pipeline = Pipeline(
        [
            ("preprocess", preprocessing(frame)),
            ("regressor", DummyRegressor(strategy="constant", constant=60)),
        ]
    ).fit(frame, np.array([rows[0]["Fundamental_Score"]]))
    return {
        "task": "score_regression",
        "target": "Fundamental_Score",
        "pipeline": pipeline,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "input_features": list(frame),
        "contextual_features": True,
        "extended_features": True,
        "sklearn_version": sklearn.__version__,
        "snapshot_date": "2026-10-05",
    }


def test_fixed_score_bands_include_all_boundaries_and_bounds():
    values = np.array([-2, 0, 39.99, 40, 59.99, 60, 74.99, 75, 89.99, 90, 100, 102])
    np.testing.assert_array_equal(score_codes(values), [0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4])
    np.testing.assert_array_equal(bounded_scores(np.array([-2, 102])), [0, 100])


def test_displayed_rounded_score_determines_its_label():
    values = np.array([39.999, 59.999, 74.999, 89.999])
    np.testing.assert_array_equal(bounded_scores(values), [40, 60, 75, 90])
    np.testing.assert_array_equal(score_codes(values), [1, 2, 3, 4])


@pytest.mark.parametrize("values", [[np.nan], [np.inf], [-np.inf], [[80]]])
def test_nonfinite_or_multidimensional_predictions_fail(values):
    with pytest.raises(ValueError, match="finite one-dimensional"):
        bounded_scores(np.array(values))


def test_regression_uses_predicted_score_and_preserves_rule_audit(score_observation, score_bundle):
    rows, _ = clean_rows([score_observation], date(2026, 10, 5))
    rule_score = rows[0]["Fundamental_Score"]
    result = predict_rows(score_bundle, rows)[0]
    assert result["Fundamental_Score"] == result["Model_Score"] == 60
    assert result["Fundamental"] == result["Model_Label"] == "Moderate"
    assert result["Rule_Fundamental_Score"] == rule_score
    assert result["Rule_Fundamental"] == rows[0]["Fundamental"]
    assert result["Model_Probability"] is None  # A continuous score is not a probability.
    assert rows[0]["Fundamental_Score"] == rule_score


def test_limited_row_never_receives_a_filled_target(score_observation, score_bundle):
    score_observation["Business_Type"] = "Regulated_Financial"
    rows, _ = clean_rows([score_observation], date(2026, 10, 5))
    result = predict_rows(score_bundle, rows)[0]
    assert result["Fundamental"] == LIMITED
    assert result["Fundamental_Score"] is None and result["Model_Score"] is None


def test_incorrect_regression_target_is_rejected(score_observation, score_bundle):
    rows, _ = clean_rows([score_observation], date(2026, 10, 5))
    score_bundle["target"] = "Label_Code"
    with pytest.raises(ValueError, match="target must be Fundamental_Score"):
        predict_rows(score_bundle, rows)


def test_scores_never_enter_regression_features(score_observation):
    rows, _ = clean_rows([score_observation], date(2026, 10, 5))
    before = feature_frame(rows, extended=True)
    rows[0].update(Fundamental_Score=100, Fundamental="Very Weak", Rule_Fundamental_Score=3)
    after = feature_frame(rows, extended=True)
    pd.testing.assert_frame_equal(before, after)
    assert not any("Score" in col or "Fundamental" in col for col in after)


def test_regression_metrics_are_point_errors_and_derived_label_accuracy():
    actual = np.array([0, 39.99, 45, 60, 75, 90, 100])
    predicted = np.array([0, 40, 45, 65, 75, 85, 105])
    result = regression_measurements(actual, predicted)
    assert result["mae_points"] == pytest.approx(10.01 / 7)
    assert result["derived_labels"]["accuracy"] == pytest.approx(5 / 7)
    assert "accuracy_wilson_95_interval" not in result["derived_labels"]


def test_search_selects_score_error_and_fits_preprocessing_inside_folds():
    search = regression_search(1, [(np.array([0, 1]), np.array([2]))])
    assert search.refit == "neg_mae"
    assert list(search.estimator.named_steps) == ["features", "preprocess", "regressor"]
    assert len(ParameterGrid(search.param_grid)) == 100
    assert not hasattr(search.estimator.named_steps["preprocess"], "transformers_")


def test_regression_publication_roundtrip_and_old_generation_preserved_on_failure(
    tmp_path, score_observation, score_bundle
):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps([score_observation]))
    model = tmp_path / "model.joblib"
    joblib.dump(score_bundle, model)
    root = tmp_path / "live"
    result = publish(raw, model, root, ["TEST"])
    assert result["model_task"] == "score_regression"
    assert read_latest(root)["stocks"][0]["Fundamental_Score"] == 60
    assert result["stocks"][0]["Fundamental"] == "Moderate"
    assert "Rule_Fundamental_Score" in result["stocks"][0]
    pointer = (root / "latest.json").read_bytes()
    score_bundle["pipeline"].named_steps["regressor"].constant_ = np.array([[np.nan]])
    joblib.dump(score_bundle, model)
    with pytest.raises(ValueError, match="finite one-dimensional"):
        publish(raw, model, root, ["TEST"])
    assert (root / "latest.json").read_bytes() == pointer


def test_activation_validates_report_and_preserves_previous_model(
    tmp_path, monkeypatch, score_bundle
):
    from backend.app.fundamentals import publication
    from backend.app.fundamentals.data import sha256

    root = tmp_path / "repo"
    pointer = root / "data/models/fundamentals/active_model.json"
    output = pointer.parent / "regression"
    output.mkdir(parents=True)
    monkeypatch.setattr(publication, "ROOT", root)
    monkeypatch.setattr(publication, "ACTIVE_MODEL_POINTER", pointer)
    monkeypatch.setattr(publication, "DEFAULT_PUBLICATION", root / "live")
    previous = {"path": "data/models/fundamentals/previous/model.joblib", "sha256": "old"}
    pointer.write_text(json.dumps(previous))
    joblib.dump(score_bundle, output / "model.joblib")
    report = {
        "model_sha256": "wrong",
        "nested_cv": {"mae_points": 5, "derived_labels": {"accuracy": 0.6}},
    }
    report_path = output / "regression_report.json"
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="checksum differs"):
        activate_regression(output)
    assert json.loads(pointer.read_text()) == previous
    report["model_sha256"] = sha256(output / "model.joblib")
    report_path.write_text(json.dumps(report))
    activate_regression(output)
    assert json.loads(pointer.read_text())["task"] == "score_regression"
    assert json.loads((output / "previous_active_model.json").read_text()) == previous
    with pytest.raises(ValueError, match="cannot overwrite the active model"):
        train_regression(
            tmp_path / "not-opened.csv", tmp_path / "not-opened.json", output, tmp_path
        )


def test_activation_rejects_external_model_directory(tmp_path):
    with pytest.raises(ValueError, match="inside the fundamentals model directory"):
        activate_regression(tmp_path)
