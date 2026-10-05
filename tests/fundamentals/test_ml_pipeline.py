"""Tests for evidence handling, leakage prevention, inference and safe publication."""

import copy
import json
from datetime import UTC, date, datetime

import joblib
import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from backend.app.fundamentals.data import (
    BASE_NUMERIC,
    LIMITED,
    POLICY_VERSION,
    SCHEMA_VERSION,
    clean_rows,
    feature_frame,
)
from backend.app.fundamentals.publication import publish, read_latest, run_lock
from backend.app.fundamentals.training import predict_rows, preprocessing
from jobs.refresh_fundamentals import normal_session_finished


@pytest.fixture
def observation():
    history = {"annual": {}, "quarters": {}, "balance": {}, "cash": {}, "returns": {}}
    for year in range(2023, 2027):
        period = f"{year}-03-31"
        factor = 1.1 ** (year - 2023)
        history["annual"][period] = {
            "months": 12,
            "revenue": 1000 * factor,
            "operating": 200 * factor,
            "net": 100 * factor,
            "interest": 10 * factor,
            "ebit": 180 * factor,
            "margin": 20,
            "payout": 30,
        }
        history["balance"][period] = {"debt": 100, "equity": 200, "de": 0.5}
        history["cash"][period] = 110 * factor
        history["returns"][period] = 20
    for year, factor in [(2025, 1), (2026, 1.1)]:
        history["quarters"][f"{year}-06-30"] = {
            "revenue": 250 * factor,
            "net": 25 * factor,
            "ebit": 45 * factor,
        }
    row = {k: 0 for k in BASE_NUMERIC}
    row.update(
        Symbol="TEST",
        Company="Test Ltd",
        Sector="Information Technology",
        Broad_Industry="IT - Software",
        Industry="Software",
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
        Promoter_Holding=50,
        _equity=200,
        _net_profit=130,
        _last_annual_profit=130,
        _financial_history=history,
        Promoter_Encumbrance=0,
        Encumbrance_Total_Capital=0,
    )
    return row


@pytest.fixture
def model(tmp_path, observation):
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    frame = feature_frame(rows)
    pipeline = Pipeline(
        [
            ("preprocess", preprocessing(frame)),
            ("classifier", DummyClassifier(strategy="constant", constant=4)),
        ]
    )
    pipeline.fit(pd.concat([frame] * 5), np.arange(5))
    bundle = {
        "pipeline": pipeline,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "input_features": list(frame),
        "contextual_features": True,
        "sklearn_version": sklearn.__version__,
        "snapshot_date": "2026-10-05",
    }
    path = tmp_path / "model.joblib"
    joblib.dump(bundle, path)
    return path, bundle


def test_cleaning_keeps_missing_distinct_from_true_zero(observation):
    observation.update(FII_QoQ=None, Promoter_Pledge=0)
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    assert rows[0]["FII_QoQ"] is None
    assert rows[0]["Promoter_Pledge"] == 0


def test_stale_statements_cannot_support_rating(observation):
    observation["Balance_Sheet_Period"] = "2017-03-31"
    rows, audit = clean_rows([observation], date(2026, 10, 5))
    assert rows[0]["Debt_Equity"] is None
    assert rows[0]["Fundamental"] == LIMITED
    assert rows[0]["Fundamental_Score"] is None
    assert audit["issues"]


def test_cleaning_does_not_mutate_source(observation):
    original = copy.deepcopy(observation)
    clean_rows([observation], date(2026, 10, 5))
    assert observation == original


def test_filled_bank_fields_do_not_produce_industrial_rating(observation):
    observation["Business_Type"] = "Regulated_Financial"
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    assert rows[0]["Fundamental"] == LIMITED


def test_unknown_pledge_does_not_mean_unpledged(observation):
    observation["Promoter_Pledge"] = None
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    assert rows[0]["Fundamental"] == LIMITED


def test_invalid_holdings_are_missing(observation):
    observation["FII_Holding"] = 120
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    assert rows[0]["FII_Holding"] is None


def test_duplicates_fail_closed(observation):
    with pytest.raises(ValueError, match="duplicate"):
        clean_rows([observation, copy.deepcopy(observation)], date(2026, 10, 5))


def test_future_period_not_used(observation):
    observation["_financial_history"]["annual"]["2027-03-31"] = {"months": 12, "net": 100000}
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    assert rows[0]["_context_metrics"]["Annual_Context_Period"] == "2026-03-31"


def test_score_assessments_and_company_identity_cannot_leak(observation):
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    before = feature_frame(rows)
    rows[0].update(
        Fundamental="Weak",
        Fundamental_Score=0,
        Context_Assessments={"Cash": "Weak"},
        Eligibility_Profile="Weak",
        Company="Different Company",
        Fundamental_Raw_Score=100,
    )
    pd.testing.assert_frame_equal(before, feature_frame(rows))
    assert "Symbol" not in before and "Company" not in before


def test_imputation_fit_uses_only_training_and_accepts_new_sector():
    train = pd.DataFrame({"Debt_Equity": [0, 1, np.nan], "Sector": ["IT"] * 3})
    test = pd.DataFrame({"Debt_Equity": [1000, np.nan], "Sector": ["NEW"] * 2})
    transform = preprocessing(train).fit(train)
    assert transform.named_transformers_["numeric"]["impute"].statistics_[0] == 0.5
    assert np.isfinite(transform.transform(test)).all()


def test_limited_rows_are_gated_before_prediction(observation, model):
    observation["Business_Type"] = "Regulated_Financial"
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    result = predict_rows(model[1], rows)[0]
    assert result["Model_Label"] == LIMITED and result["Model_Probability"] is None


def test_incompatible_model_is_rejected(observation, model):
    rows, _ = clean_rows([observation], date(2026, 10, 5))
    model[1]["policy_version"] = "OLD"
    with pytest.raises(ValueError, match="version mismatch"):
        predict_rows(model[1], rows)


def test_publication_complete_and_failure_retains_previous(tmp_path, observation, model):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps([observation]))
    root = tmp_path / "live"
    result = publish(raw, model[0], root, ["TEST"])
    assert read_latest(root)["stocks"] == result["stocks"]
    pointer = (root / "latest.json").read_bytes()
    with pytest.raises(ValueError, match="Incomplete"):
        publish(raw, model[0], root, ["TEST", "MISSING"])
    assert (root / "latest.json").read_bytes() == pointer


def test_concurrent_refresh_is_rejected_and_lock_released(tmp_path):
    with (
        run_lock(tmp_path),
        pytest.raises(RuntimeError, match="already running"),
        run_lock(tmp_path),
    ):
        pass
    with run_lock(tmp_path):
        pass


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-10-06T10:59:00+00:00", False),
        ("2026-10-06T11:00:00+00:00", True),
        ("2026-10-20T12:00:00+00:00", False),
        ("2026-10-10T12:00:00+00:00", False),
    ],
)
def test_after_close_and_holiday_guards(timestamp, expected):
    calendar = {"year": 2026, "holidays": ["2026-10-20"]}
    assert normal_session_finished(datetime.fromisoformat(timestamp), calendar) is expected


def test_wrong_year_calendar_fails_closed():
    with pytest.raises(ValueError, match="current year"):
        normal_session_finished(datetime(2027, 1, 4, 12, tzinfo=UTC), {"year": 2026})
