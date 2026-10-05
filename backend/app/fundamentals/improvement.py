"""Evaluate improved financial representations with paired nested cross-validation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, VotingClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, make_scorer
from sklearn.model_selection import GridSearchCV, RepeatedStratifiedKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from backend.app.fundamentals.data import (
    LABEL_ENCODING,
    LIMITED,
    POLICY_VERSION,
    SCHEMA_VERSION,
    feature_frame,
    load_snapshot,
    sha256,
)
from backend.app.fundamentals.estimators import (
    BalancedClassifier,
    FinancialInteractions,
    OrdinalClassifier,
    signed_log,
)
from backend.app.fundamentals.training import SEED, measurements, predict_rows

EVALUATION_SEED = SEED + 2
OUTER_FOLDS = 5
OUTER_REPEATS = 2


def improvement_search(workers: int, cv: Any) -> GridSearchCV:
    preprocess = ColumnTransformer(
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
                        ("log", FunctionTransformer(signed_log, feature_names_out="one-to-one")),
                        ("scale", StandardScaler()),
                    ]
                ),
                make_column_selector(dtype_include=np.number),
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                make_column_selector(dtype_exclude=np.number),
            ),
        ],
        sparse_threshold=0,
    )
    trees = ExtraTreesClassifier(
        n_estimators=220, class_weight="balanced", n_jobs=1, random_state=SEED
    )
    hist = HistGradientBoostingClassifier(
        max_iter=160, learning_rate=0.08, class_weight="balanced", random_state=SEED
    )
    xgb = BalancedClassifier(
        XGBClassifier(
            n_estimators=180,
            n_jobs=1,
            random_state=SEED,
            objective="multi:softprob",
            eval_metric="mlogloss",
            tree_method="hist",
        )
    )
    ordinal = OrdinalClassifier(
        HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.08,
            min_samples_leaf=5,
            l2_regularization=1,
            random_state=SEED,
        )
    )
    voting = VotingClassifier(
        estimators=[
            ("trees", clone(trees).set_params(max_features=0.8, min_samples_leaf=1)),
            (
                "hist",
                clone(hist).set_params(max_leaf_nodes=7, min_samples_leaf=5, l2_regularization=1),
            ),
            (
                "xgb",
                clone(xgb).set_params(
                    estimator__max_depth=3, estimator__learning_rate=0.08, estimator__reg_lambda=3
                ),
            ),
        ],
        voting="soft",
        n_jobs=1,
    )
    grids: list[dict[str, Any]] = [
        {
            "classifier": [trees],
            "classifier__max_features": ["sqrt", 0.8],
            "classifier__min_samples_leaf": [1, 3],
            "classifier__max_depth": [None, 8],
        },
        {
            "classifier": [hist],
            "classifier__max_leaf_nodes": [7, 15],
            "classifier__min_samples_leaf": [3, 5],
            "classifier__l2_regularization": [1, 5],
        },
        {
            "classifier": [xgb],
            "classifier__estimator__max_depth": [2, 3],
            "classifier__estimator__learning_rate": [0.05, 0.1],
            "classifier__estimator__reg_lambda": [1, 5],
        },
        {
            "classifier": [ordinal],
            "classifier__estimator__max_leaf_nodes": [7, 15],
            "classifier__balance": [False, True],
        },
        {"classifier": [voting], "classifier__weights": [None, [1, 2, 1]]},
    ]
    for grid in grids:
        grid.update({"features__view": ["rich", "compact"], "selection__k": [30, "all"]})
    pipeline = Pipeline(
        [
            ("features", FinancialInteractions()),
            ("preprocess", preprocess),
            ("selection", SelectKBest(f_classif)),
            ("classifier", trees),
        ]
    )
    return GridSearchCV(
        pipeline,
        grids,
        cv=cv,
        n_jobs=workers,
        refit="accuracy",
        scoring={
            "accuracy": "accuracy",
            "balanced_accuracy": "balanced_accuracy",
            "macro_f1": make_scorer(f1_score, average="macro", zero_division=0),
        },
        error_score="raise",
    )


def configuration(params: dict[str, Any]) -> dict[str, Any]:
    result = {k: type(v).__name__ if k == "classifier" else v for k, v in params.items()}
    estimator = params.get("classifier")
    if isinstance(estimator, (OrdinalClassifier, BalancedClassifier)):
        result["classifier_base"] = type(estimator.estimator).__name__
    return result


def clustered_comparison(old_correct: np.ndarray, new_correct: np.ndarray) -> dict[str, Any]:
    # Resample stock IDs, retaining both repeated validation appearances together.
    rng = np.random.default_rng(EVALUATION_SEED)
    indices = rng.integers(0, len(old_correct), size=(10000, len(old_correct)))
    old_average = old_correct.mean(axis=1)
    new_average = new_correct.mean(axis=1)
    gains = (new_average - old_average)[indices].mean(axis=1)
    values = new_average[indices].mean(axis=1)
    return {
        "accuracy_gain": float(new_correct.mean() - old_correct.mean()),
        "paired_gain_bootstrap_95_interval": np.quantile(gains, [0.025, 0.975]).tolist(),
        "new_accuracy_stock_bootstrap_95_interval": np.quantile(values, [0.025, 0.975]).tolist(),
        "bootstrap_unit": "Stock; repeated appearances remain together",
        "interval_limit": (
            "Descriptive bootstrap; correlated CV training sets and prior development remain"
        ),
    }


def improve(
    csv_path: Path, raw_path: Path, baseline_path: Path, output: Path, workers: int = 2
) -> dict[str, Any]:
    rows, audit = load_snapshot(csv_path, raw_path)
    eligible = [r for r in rows if r["Fundamental"] != LIMITED]
    y = np.array([LABEL_ENCODING[r["Fundamental"]] for r in eligible])
    if len(set(y)) != 5 or min(Counter(y).values()) < 6:
        raise ValueError("Need all five health classes and at least six stocks in each")
    baseline_bundle = joblib.load(baseline_path)
    old_frame = feature_frame(eligible, contextual=baseline_bundle["contextual_features"])
    extended = feature_frame(eligible, contextual=True, extended=True)
    output.mkdir(parents=True, exist_ok=True)
    outer = RepeatedStratifiedKFold(
        n_splits=OUTER_FOLDS, n_repeats=OUTER_REPEATS, random_state=EVALUATION_SEED
    )
    splits = list(outer.split(extended, y))
    manifest = [
        {
            "fold": i + 1,
            "repeat": i // OUTER_FOLDS + 1,
            "training_symbols": [eligible[j]["Symbol"] for j in train],
            "validation_symbols": [eligible[j]["Symbol"] for j in valid],
        }
        for i, (train, valid) in enumerate(splits)
    ]
    # Freeze the split plan before any fit. No searching different seeds/splits for accuracy.
    (output / "outer_splits.json").write_text(json.dumps(manifest, indent=2))
    old_predictions = np.full((len(y), OUTER_REPEATS), -1, dtype=int)
    new_predictions = np.full_like(old_predictions, -1)
    folds = []
    for i, (train, valid) in enumerate(splits):
        old = clone(baseline_bundle["pipeline"]).fit(old_frame.iloc[train], y[train])
        predicted_old = old.predict(old_frame.iloc[valid])
        inner = StratifiedKFold(n_splits=3, shuffle=True, random_state=EVALUATION_SEED + i + 1)
        search = improvement_search(workers, inner)
        search.fit(extended.iloc[train], y[train])
        predicted = search.predict(extended.iloc[valid])
        repeat = i // OUTER_FOLDS
        old_predictions[valid, repeat] = predicted_old
        new_predictions[valid, repeat] = predicted
        fold = {
            "fold": i + 1,
            "repeat": repeat + 1,
            "baseline_accuracy": float(accuracy_score(y[valid], predicted_old)),
            "new_accuracy": float(accuracy_score(y[valid], predicted)),
            "new_macro_f1": float(f1_score(y[valid], predicted, average="macro", zero_division=0)),
            "inner_selection_accuracy": float(search.best_score_),
            "selected_parameters": configuration(search.best_params_),
        }
        folds.append(fold)
        (output / "progress.json").write_text(
            json.dumps({"completed_folds": i + 1, "folds": folds}, indent=2)
        )
        print(
            f"Nested fold {i + 1}/{len(splits)}: baseline {fold['baseline_accuracy']:.2%}, "
            f"improved {fold['new_accuracy']:.2%}",
            flush=True,
        )
    if (new_predictions < 0).any() or (old_predictions < 0).any():
        raise AssertionError("Incomplete out-of-fold predictions")
    truth = np.repeat(y, OUTER_REPEATS)
    old_metrics = measurements(truth, old_predictions.ravel())
    new_metrics = measurements(truth, new_predictions.ravel())
    for result in [old_metrics, new_metrics]:
        result.pop("accuracy_wilson_95_interval")
        result.update(
            unique_stocks=len(y), validation_appearances=len(truth), repetitions=OUTER_REPEATS
        )
    comparison = clustered_comparison(old_predictions == y[:, None], new_predictions == y[:, None])
    final_cv = RepeatedStratifiedKFold(n_splits=3, n_repeats=2, random_state=EVALUATION_SEED)
    final_search = improvement_search(workers, final_cv).fit(extended, y)
    final = final_search.best_estimator_
    bundle = {
        "pipeline": final,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "input_features": list(extended),
        "label_encoding": LABEL_ENCODING,
        "contextual_features": True,
        "extended_features": True,
        "seed": EVALUATION_SEED,
        "sklearn_version": sklearn.__version__,
        "snapshot_date": rows[0]["Snapshot_Date"],
        "source_csv_sha256": sha256(csv_path),
        "source_raw_sha256": sha256(raw_path),
        "model_role": "Rule-label approximation; contextual policy publishes final labels",
    }
    joblib.dump(bundle, output / "model.joblib")
    reloaded = joblib.load(output / "model.joblib")
    if not np.array_equal(final.predict(extended), reloaded["pipeline"].predict(extended)):
        raise AssertionError("Model serialization changed predictions")
    inference = predict_rows(reloaded, rows)
    (output / "stock_predictions.json").write_text(json.dumps(inference, indent=2, allow_nan=False))
    oof = [
        {
            "Symbol": r["Symbol"],
            "Actual_Label": r["Fundamental"],
            "baseline_codes": old_predictions[i].tolist(),
            "new_codes": new_predictions[i].tolist(),
        }
        for i, r in enumerate(eligible)
    ]
    (output / "out_of_fold_predictions.json").write_text(json.dumps(oof, indent=2))
    from sklearn.model_selection import ParameterGrid

    candidates = [
        {
            "parameters": configuration(params),
            "cv_accuracy": float(final_search.cv_results_["mean_test_accuracy"][i]),
            "cv_macro_f1": float(final_search.cv_results_["mean_test_macro_f1"][i]),
        }
        for i, params in enumerate(final_search.cv_results_["params"])
    ]
    approved = (
        new_metrics["accuracy"] > old_metrics["accuracy"]
        and new_metrics["macro_f1"] >= old_metrics["macro_f1"]
    )
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "snapshot_date": rows[0]["Snapshot_Date"],
        "total_stocks": len(rows),
        "assessable_stocks": len(y),
        "limited_stocks": len(rows) - len(y),
        "class_counts": dict(Counter(r["Fundamental"] for r in rows)),
        "evaluation": (
            "Five-fold nested stratified CV, two repeats; same folds for baseline and improvement"
        ),
        "outer_seed": EVALUATION_SEED,
        "baseline_same_splits": old_metrics,
        "improved_nested_cv": new_metrics,
        "comparison": comparison,
        "folds": folds,
        "final_parameters": configuration(final_search.best_params_),
        "final_selection_cv_accuracy": float(final_search.best_score_),
        "configuration_count": len(ParameterGrid(final_search.param_grid)),
        "candidates": candidates,
        "data_audit": audit,
        "model_sha256": sha256(output / "model.joblib"),
        "baseline_model_sha256": sha256(baseline_path),
        "improved_by_paired_metrics": approved,
        "limitations": [
            "Previously examined dataset, not a new independent holdout",
            "The original 32-stock test is not reused as a fresh test",
            "Generated labels; agreement does not validate real-world fundamental quality",
            "One snapshot date; no future-period accuracy established",
            "Seven stocks in each weak class; limited minority-class evidence",
            "All hyperparameter/feature selection occurs inside each outer training fold",
            "Final model refitted on all 156 assessable stocks after evaluation",
            "Published Fundamental remains the contextual policy label",
        ],
    }
    (output / "improvement_report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    print(
        json.dumps(
            {
                "baseline_cv": old_metrics["accuracy"],
                "improved_cv": new_metrics["accuracy"],
                "macro_f1": new_metrics["macro_f1"],
                "improved": approved,
            },
            indent=2,
        ),
        flush=True,
    )
    return report
