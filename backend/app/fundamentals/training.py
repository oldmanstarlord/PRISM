"""Reproducible, leakage-controlled experiments on rule-generated labels."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    make_scorer,
)
from sklearn.model_selection import (
    GridSearchCV,
    RepeatedStratifiedKFold,
    StratifiedKFold,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

from backend.app.fundamentals.data import (
    CLASSES,
    LABEL_ENCODING,
    LIMITED,
    POLICY_VERSION,
    SCHEMA_VERSION,
    feature_frame,
    load_snapshot,
    sha256,
    table_payload,
)
from backend.app.fundamentals.scores import bounded_scores, score_codes

SEED = 20261006


def preprocessing(frame: pd.DataFrame) -> ColumnTransformer:
    categories = [c for c in ["Sector", "Broad_Industry"] if c in frame]
    numeric = [c for c in frame if c not in categories]
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        (
                            "impute",
                            SimpleImputer(
                                strategy="median", add_indicator=True, keep_empty_features=True
                            ),
                        ),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categories,
            ),
        ],
        sparse_threshold=0,
        verbose_feature_names_out=True,
    )


def parameter_grid() -> list[dict[str, Any]]:
    """Bounded search appropriate to 156 observations; no synthetic data/oversampling."""
    return [
        {
            "classifier": [LogisticRegression(max_iter=3000, random_state=SEED)],
            "classifier__C": [0.01, 0.1, 1, 10],
            "classifier__class_weight": [None, "balanced"],
        },
        {
            "classifier": [SVC(probability=True, random_state=SEED)],
            "classifier__C": [0.1, 1, 10, 100],
            "classifier__gamma": ["scale", 0.01],
            "classifier__class_weight": ["balanced"],
        },
        {
            "classifier": [RandomForestClassifier(n_estimators=180, n_jobs=1, random_state=SEED)],
            "classifier__max_depth": [None, 5],
            "classifier__min_samples_leaf": [1, 3],
            "classifier__max_features": ["sqrt", 0.8],
            "classifier__class_weight": ["balanced"],
        },
        {
            "classifier": [ExtraTreesClassifier(n_estimators=180, n_jobs=1, random_state=SEED)],
            "classifier__max_depth": [None, 5],
            "classifier__min_samples_leaf": [1, 3],
            "classifier__max_features": ["sqrt", 0.8],
            "classifier__class_weight": ["balanced"],
        },
        {
            "classifier": [HistGradientBoostingClassifier(random_state=SEED, max_iter=120)],
            "classifier__learning_rate": [0.05, 0.1],
            "classifier__max_leaf_nodes": [7, 15],
            "classifier__min_samples_leaf": [5, 10],
            "classifier__l2_regularization": [1],
        },
        {
            "classifier": [
                XGBClassifier(
                    n_jobs=1,
                    random_state=SEED,
                    objective="multi:softprob",
                    eval_metric="mlogloss",
                    tree_method="hist",
                )
            ],
            "classifier__max_depth": [2, 3],
            "classifier__n_estimators": [100, 200],
            "classifier__learning_rate": [0.03, 0.1],
            "classifier__reg_lambda": [5],
            "classifier__subsample": [0.9],
            "classifier__colsample_bytree": [0.9],
        },
    ]


def make_search(frame: pd.DataFrame, cv: Any, workers: int) -> GridSearchCV:
    pipeline = Pipeline(
        [("preprocess", preprocessing(frame)), ("classifier", LogisticRegression())]
    )
    return GridSearchCV(
        pipeline,
        parameter_grid(),
        cv=cv,
        n_jobs=workers,
        refit="accuracy",
        scoring={
            "accuracy": "accuracy",
            "balanced_accuracy": "balanced_accuracy",
            "macro_f1": make_scorer(f1_score, average="macro", zero_division=0),
        },
        error_score="raise",
        return_train_score=True,
    )


def params_json(params: dict[str, Any]) -> dict[str, Any]:
    return {k: type(v).__name__ if k == "classifier" else v for k, v in params.items()}


def measurements(y: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    accuracy = float(accuracy_score(y, predicted))
    n, z = len(y), 1.96
    center = (accuracy + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(accuracy * (1 - accuracy) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "accuracy": accuracy,
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "macro_f1": float(f1_score(y, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y, predicted, average="weighted", zero_division=0)),
        "sample_count": n,
        "correct": int(np.sum(y == predicted)),
        "accuracy_wilson_95_interval": [center - half, center + half],
        "confusion_matrix": confusion_matrix(y, predicted, labels=list(range(5))).tolist(),
        "class_order": CLASSES,
        "classification_report": classification_report(
            y,
            predicted,
            labels=list(range(5)),
            target_names=CLASSES,
            output_dict=True,
            zero_division=0,
        ),
    }


def predict_rows(bundle: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if bundle["schema_version"] != SCHEMA_VERSION or bundle["policy_version"] != POLICY_VERSION:
        raise ValueError("Model/schema/policy version mismatch; retrain explicitly")
    frame = feature_frame(
        rows,
        contextual=bundle["contextual_features"],
        extended=bundle.get("extended_features", False),
    )
    if list(frame.columns) != bundle["input_features"]:
        raise ValueError("Prediction feature schema differs from training")
    eligible = [i for i, r in enumerate(rows) if r["Fundamental"] != LIMITED]
    if bundle.get("task") == "score_regression":
        if bundle.get("target") != "Fundamental_Score":
            raise ValueError("Regression model target must be Fundamental_Score")
        learned_scores = {}
        if eligible:
            scores = bounded_scores(bundle["pipeline"].predict(frame.iloc[eligible]))
            if len(scores) != len(eligible):
                raise ValueError("Regression prediction count differs from eligible rows")
            codes = score_codes(scores)
            learned_scores = {
                i: (float(score), CLASSES[int(code)])
                for i, score, code in zip(eligible, scores, codes, strict=True)
            }
        results = []
        for i, row in enumerate(rows):
            score, label = learned_scores.get(i, (None, LIMITED))
            agrees = None if score is None else label == row["Fundamental"]
            results.append(
                {
                    "Symbol": row["Symbol"],
                    "Company": row["Company"],
                    "Fundamental": label,
                    "Fundamental_Score": score,
                    "Rule_Fundamental": row["Fundamental"],
                    "Rule_Fundamental_Score": row["Fundamental_Score"],
                    "Model_Label": label,
                    "Model_Score": score,
                    "Model_Probability": None,
                    "Model_Agrees": agrees,
                    "Assessment_Status": "Insufficient data"
                    if score is None
                    else "Regression estimate; rule label agrees"
                    if agrees
                    else "Regression estimate; rule label differs",
                }
            )
        return results
    learned: dict[int, tuple[str, float]] = {}
    if eligible:
        estimator = bundle["pipeline"]
        predictions = estimator.predict(frame.iloc[eligible])
        probabilities = estimator.predict_proba(frame.iloc[eligible])
        classes = list(estimator.classes_)
        for i, p, prob in zip(eligible, predictions, probabilities, strict=True):
            learned[i] = (CLASSES[int(p)], float(prob[classes.index(p)]))
    result = []
    for i, row in enumerate(rows):
        label, probability = learned.get(i, (LIMITED, None))
        result.append(
            {
                "Symbol": row["Symbol"],
                "Company": row["Company"],
                "Fundamental": row["Fundamental"],
                "Fundamental_Score": row["Fundamental_Score"],
                "Model_Label": label,
                "Model_Probability": probability,
                "Model_Agrees": None if label == LIMITED else label == row["Fundamental"],
                "Assessment_Status": "Insufficient data"
                if label == LIMITED
                else "Rule and model agree"
                if label == row["Fundamental"]
                else "Rule/model disagreement",
            }
        )
    return result


def train(csv_path: Path, raw_path: Path, output: Path, workers: int = 2) -> dict[str, Any]:
    rows, audit = load_snapshot(csv_path, raw_path)
    output.mkdir(parents=True, exist_ok=True)
    eligible = [r for r in rows if r["Fundamental"] != LIMITED]
    y = np.array([LABEL_ENCODING[r["Fundamental"]] for r in eligible])
    if len(set(y)) != 5 or min(Counter(y).values()) < 6:
        raise ValueError("Need all five assessable classes and at least six observations per class")
    train_indices, test_indices = train_test_split(
        np.arange(len(y)), test_size=0.2, stratify=y, random_state=SEED
    )
    splits = {
        "seed": SEED,
        "train_symbols": [eligible[i]["Symbol"] for i in train_indices],
        "test_symbols": [eligible[i]["Symbol"] for i in test_indices],
    }
    (output / "split_manifest.json").write_text(json.dumps(splits, indent=2))
    cv = RepeatedStratifiedKFold(n_splits=3, n_repeats=2, random_state=SEED)
    experiments, searches, frames = [], {}, {}
    for contextual in [False, True]:
        name = "contextual" if contextual else "requested_fields"
        frame = feature_frame(eligible, contextual)
        print(f"Tuning {name}: {frame.shape[1]} inputs, six model families", flush=True)
        search = make_search(frame, cv, workers)
        search.fit(frame.iloc[train_indices], y[train_indices])
        searches[name], frames[name] = search, frame
        candidates = []
        for i, params in enumerate(search.cv_results_["params"]):
            candidates.append(
                {
                    "parameters": params_json(params),
                    "cv_accuracy": float(search.cv_results_["mean_test_accuracy"][i]),
                    "cv_accuracy_std": float(search.cv_results_["std_test_accuracy"][i]),
                    "cv_balanced_accuracy": float(
                        search.cv_results_["mean_test_balanced_accuracy"][i]
                    ),
                    "cv_macro_f1": float(search.cv_results_["mean_test_macro_f1"][i]),
                    "training_accuracy": float(search.cv_results_["mean_train_accuracy"][i]),
                }
            )
        experiments.append(
            {
                "feature_set": name,
                "input_count": frame.shape[1],
                "best_parameters": params_json(search.best_params_),
                "best_cv_accuracy": float(search.best_score_),
                "candidates": candidates,
            }
        )
        print(f"{name} best CV accuracy: {search.best_score_:.4f}", flush=True)
    selected_name = max(searches, key=lambda n: searches[n].best_score_)
    selected = searches[selected_name]
    frame = frames[selected_name]
    # Single evaluation of the untouched holdout after feature/family/parameter selection.
    holdout_prediction = selected.predict(frame.iloc[test_indices])
    holdout = measurements(y[test_indices], holdout_prediction)
    dummy = DummyClassifier(strategy="most_frequent").fit(
        frame.iloc[train_indices], y[train_indices]
    )
    baseline = measurements(y[test_indices], dummy.predict(frame.iloc[test_indices]))
    holdout_rows = [
        {
            "Symbol": eligible[i]["Symbol"],
            "Actual_Label": CLASSES[int(actual)],
            "Predicted_Label": CLASSES[int(predicted)],
            "Correct": bool(actual == predicted),
        }
        for i, actual, predicted in zip(
            test_indices, y[test_indices], holdout_prediction, strict=True
        )
    ]
    # Outer folds evaluate the entire selection procedure (including feature-set choice).
    # They use only development stocks; holdout stocks stay excluded from this diagnostic.
    nested_results, nested_truth, nested_predictions = [], [], []
    outer = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED + 1)
    for fold, (inner_train, outer_test) in enumerate(
        outer.split(train_indices, y[train_indices]), 1
    ):
        fits = {}
        for name, x in frames.items():
            inner = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED + fold)
            fitted = make_search(x, inner, workers)
            fitted.fit(x.iloc[train_indices[inner_train]], y[train_indices[inner_train]])
            fits[name] = fitted
        winner = max(fits, key=lambda n: fits[n].best_score_)
        predicted = fits[winner].predict(frames[winner].iloc[train_indices[outer_test]])
        truth = y[train_indices[outer_test]]
        nested_results.append(
            {
                "fold": fold,
                "feature_set": winner,
                "parameters": params_json(fits[winner].best_params_),
                "accuracy": float(accuracy_score(truth, predicted)),
                "macro_f1": float(f1_score(truth, predicted, average="macro", zero_division=0)),
                "validation_symbols": [eligible[i]["Symbol"] for i in train_indices[outer_test]],
            }
        )
        nested_truth.extend(truth)
        nested_predictions.extend(predicted)
        print(f"Nested fold {fold}/3 accuracy: {nested_results[-1]['accuracy']:.4f}", flush=True)
    nested = measurements(np.array(nested_truth), np.array(nested_predictions))
    nested.update(
        folds=nested_results, accuracy_std=float(np.std([f["accuracy"] for f in nested_results]))
    )
    # Freeze selected configuration, then refit on all usable stocks for the delivered model.
    final = clone(selected.best_estimator_).fit(frame, y)
    bundle = {
        "pipeline": final,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "input_features": list(frame.columns),
        "label_encoding": LABEL_ENCODING,
        "contextual_features": selected_name == "contextual",
        "seed": SEED,
        "sklearn_version": sklearn.__version__,
        "snapshot_date": rows[0]["Snapshot_Date"],
        "source_csv_sha256": sha256(csv_path),
        "source_raw_sha256": sha256(raw_path),
        "model_role": "Rule-label approximation; contextual policy publishes final labels",
    }
    joblib.dump(bundle, output / "model.joblib")
    reloaded = joblib.load(output / "model.joblib")
    if not np.array_equal(final.predict(frame), reloaded["pipeline"].predict(frame)):
        raise AssertionError("Serialized model predictions changed")
    names = final.named_steps["preprocess"].get_feature_names_out()
    encoded = pd.DataFrame(final.named_steps["preprocess"].transform(frame), columns=names)
    encoded.insert(0, "Symbol", [r["Symbol"] for r in eligible])
    encoded["Target_Code"] = y
    encoded["Fundamental"] = [r["Fundamental"] for r in eligible]
    cleaned = pd.DataFrame(
        [
            {
                **{
                    k: r.get(k)
                    for k in ["Symbol", "Company", "Sector"]
                    + list(feature_frame(rows).columns.difference(["Sector"]))
                },
                **feature_frame([r]).iloc[0].to_dict(),
                "Fundamental": r["Fundamental"],
                "Fundamental_Score": r["Fundamental_Score"],
            }
            for r in rows
        ]
    )
    predictions = pd.DataFrame(predict_rows(reloaded, rows))
    outputs = {
        "cleaned_fundamentals.csv": table_payload(cleaned),
        "encoded_training.csv": table_payload(encoded),
        "stock_predictions.csv": table_payload(predictions),
        "holdout_predictions.csv": table_payload(pd.DataFrame(holdout_rows)),
    }
    (output / "csv_tables.json").write_text(json.dumps(outputs, allow_nan=False))
    model_hash = hashlib.sha256((output / "model.joblib").read_bytes()).hexdigest()
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "seed": SEED,
        "source_snapshot": rows[0]["Snapshot_Date"],
        "total_stocks": len(rows),
        "assessable_stocks": len(eligible),
        "limited_stocks": len(rows) - len(eligible),
        "class_counts": dict(Counter(r["Fundamental"] for r in rows)),
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "selected_feature_set": selected_name,
        "selected_model": type(final[-1]).__name__,
        "selected_parameters": params_json(selected.best_params_),
        "selection_cv_accuracy": float(selected.best_score_),
        "holdout": holdout,
        "nested_development_cv": nested,
        "majority_baseline_holdout": baseline,
        "experiments": experiments,
        "data_audit": audit,
        "model_sha256": model_hash,
        "input_features": list(frame.columns),
        "encoded_feature_count": len(names),
        "label_encoding": LABEL_ENCODING,
        "versions": {
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "joblib": joblib.__version__,
        },
        "limitations": [
            "Targets generated by contextual rules, not independently audited labels",
            "One date: future-period accuracy is not established",
            "Minority classes have few stocks; holdout intervals are wide",
            "Limited Assessment is a data gate, not a learned health class",
            "Final model refit on all eligible stocks; stock_predictions are in-sample",
            "Model probabilities are not calibrated confidence estimates",
            "The published Fundamental remains the contextual policy label",
        ],
    }
    (output / "training_report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    (output / "cleaned_snapshot.json").write_text(json.dumps(rows, indent=2, allow_nan=False))
    print(
        json.dumps(
            {
                "model": report["selected_model"],
                "holdout_accuracy": holdout["accuracy"],
                "nested_cv_accuracy": nested["accuracy"],
                "output": str(output),
            },
            indent=2,
        ),
        flush=True,
    )
    return report
