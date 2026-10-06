"""Predict observed rule scores, then apply fixed health bands without target leakage."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, make_scorer, mean_absolute_error, r2_score
from sklearn.model_selection import (
    GridSearchCV,
    ParameterGrid,
    RepeatedStratifiedKFold,
    StratifiedKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

from backend.app.fundamentals.data import (
    CLASSES,
    LABEL_ENCODING,
    LIMITED,
    POLICY_VERSION,
    SCHEMA_VERSION,
    feature_frame,
    load_snapshot,
    sha256,
)
from backend.app.fundamentals.estimators import FinancialInteractions, signed_log
from backend.app.fundamentals.improvement import (
    EVALUATION_SEED,
    OUTER_FOLDS,
    OUTER_REPEATS,
    clustered_comparison,
)
from backend.app.fundamentals.scores import SCORE_BANDS, SCORE_DECIMALS, bounded_scores, score_codes
from backend.app.fundamentals.training import SEED, measurements, predict_rows


def bounded_mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(mean_absolute_error(actual, bounded_scores(predicted)))


def bounded_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - bounded_scores(predicted)) ** 2)))


def bounded_r2(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(r2_score(actual, bounded_scores(predicted)))


def band_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(accuracy_score(score_codes(actual), score_codes(predicted)))


def regression_measurements(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    scores = bounded_scores(predicted)
    error = np.abs(actual - scores)
    labels = measurements(score_codes(actual), score_codes(scores))
    # Repeated folds are not independent observations: no binomial interval is reported.
    labels.pop("accuracy_wilson_95_interval")
    return {
        "mae_points": float(error.mean()),
        "rmse_points": bounded_rmse(actual, scores),
        "r2": bounded_r2(actual, scores),
        "median_absolute_error_points": float(np.median(error)),
        "within_5_points": float(np.mean(error <= 5)),
        "within_10_points": float(np.mean(error <= 10)),
        "derived_labels": labels,
    }


def regression_search(workers: int, cv: Any) -> GridSearchCV:
    numeric = Pipeline(
        [
            (
                "impute",
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            ),
            ("log", FunctionTransformer(signed_log, feature_names_out="one-to-one")),
            ("scale", StandardScaler()),
        ]
    )
    preprocess = ColumnTransformer(
        [
            ("numeric", numeric, make_column_selector(dtype_include=np.number)),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                make_column_selector(dtype_exclude=np.number),
            ),
        ],
        sparse_threshold=0,
    )
    pipeline = Pipeline(
        [
            ("features", FinancialInteractions()),
            ("preprocess", preprocess),
            ("regressor", Ridge()),
        ]
    )
    grids: list[dict[str, Any]] = [
        {
            "regressor": [ExtraTreesRegressor(n_estimators=220, n_jobs=1, random_state=SEED)],
            "regressor__max_features": ["sqrt", 0.8, 1.0],
            "regressor__min_samples_leaf": [1, 3],
        },
        {
            "regressor": [RandomForestRegressor(n_estimators=220, n_jobs=1, random_state=SEED)],
            "regressor__max_features": ["sqrt", 0.8, 1.0],
            "regressor__min_samples_leaf": [1, 3],
        },
        {
            "regressor": [HistGradientBoostingRegressor(max_iter=180, random_state=SEED)],
            "regressor__max_leaf_nodes": [7, 15],
            "regressor__min_samples_leaf": [3, 8],
            "regressor__l2_regularization": [1, 5],
        },
        {
            "regressor": [
                GradientBoostingRegressor(n_estimators=200, min_samples_leaf=3, random_state=SEED)
            ],
            "regressor__loss": ["squared_error", "huber", "absolute_error"],
            "regressor__max_depth": [2, 3],
            "regressor__learning_rate": [0.05, 0.1],
        },
        {
            "regressor": [
                XGBRegressor(
                    n_estimators=180,
                    n_jobs=1,
                    random_state=SEED,
                    objective="reg:squarederror",
                    tree_method="hist",
                )
            ],
            "regressor__max_depth": [2, 3],
            "regressor__learning_rate": [0.05, 0.1],
            "regressor__reg_lambda": [1, 5],
        },
        {"regressor": [Ridge()], "regressor__alpha": [0.1, 1, 10, 100]},
        {"regressor": [SVR()], "regressor__C": [10, 50, 100], "regressor__epsilon": [1, 3]},
    ]
    for grid in grids:
        grid["features__view"] = ["rich", "compact"]
    return GridSearchCV(
        pipeline,
        grids,
        cv=cv,
        n_jobs=workers,
        scoring={
            "neg_mae": make_scorer(bounded_mae, greater_is_better=False),
            "neg_rmse": make_scorer(bounded_rmse, greater_is_better=False),
            "r2": make_scorer(bounded_r2),
            "band_accuracy": make_scorer(band_accuracy),
        },
        refit="neg_mae",
        error_score="raise",
    )


def parameters(params: dict[str, Any]) -> dict[str, Any]:
    result = {k: type(v).__name__ if k == "regressor" else v for k, v in params.items()}
    model = params.get("regressor")
    family = []
    while model is not None:
        family.append(type(model).__name__)
        model = getattr(model, "regressor", getattr(model, "estimator", None))
    result["regressor_family"] = " -> ".join(family)
    return result


def parameter_value(value: Any) -> Any:
    if hasattr(value, "get_params"):
        return {
            "estimator": type(value).__name__,
            "parameters": {k: parameter_value(v) for k, v in value.get_params(deep=False).items()},
        }
    if callable(value):
        return getattr(value, "__name__", str(value))
    if isinstance(value, dict):
        return {k: parameter_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [parameter_value(v) for v in value]
    if isinstance(value, np.generic):
        return parameter_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def train_regression(
    csv_path: Path,
    raw_path: Path,
    output: Path,
    comparison_dir: Path | None = None,
    workers: int = 2,
    *,
    search_factory: Callable[[int, Any], Any] = regression_search,
    selection_metric: str = "Lowest inner-CV mean absolute score error",
    previous_regression: Path | None = None,
) -> dict[str, Any]:
    from backend.app.fundamentals.publication import ACTIVE_MODEL_POINTER, ROOT

    if ACTIVE_MODEL_POINTER.exists():
        active = json.loads(ACTIVE_MODEL_POINTER.read_text())
        if (ROOT / active["path"]).resolve() == (output / "model.joblib").resolve():
            raise ValueError("Use a new output directory; cannot overwrite the active model")
    rows, audit = load_snapshot(csv_path, raw_path)
    eligible = [r for r in rows if r["Fundamental"] != LIMITED]
    y = np.array([r["Fundamental_Score"] for r in eligible], dtype=float)
    strata = np.array([LABEL_ENCODING[r["Fundamental"]] for r in eligible])
    if not np.isfinite(y).all() or ((y < 0) | (y > 100)).any():
        raise ValueError("Regression targets must be observed finite scores in [0, 100]")
    if not np.array_equal(score_codes(y), strata):
        raise ValueError("Observed score and rule label bands disagree")
    if len(set(strata)) != 5 or min(Counter(strata).values()) < 6:
        raise ValueError("Need all five score bands and six stocks in each for stratified CV")
    frame = feature_frame(eligible, contextual=True, extended=True)
    outer = RepeatedStratifiedKFold(
        n_splits=OUTER_FOLDS, n_repeats=OUTER_REPEATS, random_state=EVALUATION_SEED
    )
    splits = list(outer.split(frame, strata))
    manifest = [
        {
            "fold": i + 1,
            "repeat": i // OUTER_FOLDS + 1,
            "training_symbols": [eligible[j]["Symbol"] for j in train],
            "validation_symbols": [eligible[j]["Symbol"] for j in valid],
        }
        for i, (train, valid) in enumerate(splits)
    ]
    # Reuse the classifier evaluation's fixed folds, never its fitted full-data predictions.
    classifier_codes = None
    if comparison_dir is not None:
        classifier_report = json.loads((comparison_dir / "improvement_report.json").read_text())
        comparison_splits = json.loads((comparison_dir / "outer_splits.json").read_text())
        if comparison_splits != manifest:
            raise ValueError("Classifier comparison uses different folds")
        if classifier_report["data_audit"]["raw_sha256"] != audit["raw_sha256"]:
            raise ValueError("Classifier comparison uses different financial observations")
        # CSV formatting repairs can alter bytes; every observation was verified against raw.
        audit["comparison_csv_bytes_unchanged"] = (
            classifier_report["data_audit"]["csv_sha256"] == audit["csv_sha256"]
        )
        classifier_oof = json.loads((comparison_dir / "out_of_fold_predictions.json").read_text())
        if [r["Symbol"] for r in classifier_oof] != [r["Symbol"] for r in eligible]:
            raise ValueError("Classifier comparison universe/order differs")
        if [r["Actual_Label"] for r in classifier_oof] != [r["Fundamental"] for r in eligible]:
            raise ValueError("Classifier comparison targets differ")
        classifier_codes = np.array([r["new_codes"] for r in classifier_oof])
        if classifier_codes.shape != (len(y), OUTER_REPEATS):
            raise ValueError("Classifier out-of-fold predictions incomplete")
    output.mkdir(parents=True, exist_ok=True)
    (output / "outer_splits.json").write_text(json.dumps(manifest, indent=2))
    predictions = np.full((len(y), OUTER_REPEATS), np.nan)
    dummy_predictions = np.full_like(predictions, np.nan)
    folds = []
    count = len(ParameterGrid(search_factory(workers, []).param_grid))
    print(f"Score regression: {len(y)} stocks, {count} configurations, 10 outer folds", flush=True)
    for i, (train, valid) in enumerate(splits):
        inner = StratifiedKFold(n_splits=3, shuffle=True, random_state=EVALUATION_SEED + i + 1)
        inner_splits = list(inner.split(frame.iloc[train], strata[train]))
        search = search_factory(workers, inner_splits).fit(frame.iloc[train], y[train])
        predicted = bounded_scores(search.predict(frame.iloc[valid]))
        dummy = DummyRegressor(strategy="median").fit(frame.iloc[train], y[train])
        repeat = i // OUTER_FOLDS
        predictions[valid, repeat] = predicted
        dummy_predictions[valid, repeat] = bounded_scores(dummy.predict(frame.iloc[valid]))
        result = regression_measurements(y[valid], predicted)
        folds.append(
            {
                "fold": i + 1,
                "repeat": repeat + 1,
                **result,
                "inner_selection_mae_points": -float(
                    search.cv_results_["mean_test_neg_mae"][search.best_index_]
                ),
                "inner_selection_band_accuracy": float(
                    search.cv_results_["mean_test_band_accuracy"][search.best_index_]
                ),
                "selected_parameters": parameters(search.best_params_),
            }
        )
        (output / "progress.json").write_text(
            json.dumps({"completed_folds": i + 1, "folds": folds}, indent=2)
        )
        print(
            f"Fold {i + 1}/10: MAE {result['mae_points']:.2f} points, "
            f"derived-label accuracy {result['derived_labels']['accuracy']:.2%}",
            flush=True,
        )
    if not np.isfinite(predictions).all() or not np.isfinite(dummy_predictions).all():
        raise AssertionError("Incomplete regression out-of-fold predictions")
    actual = np.repeat(y, OUTER_REPEATS)
    metrics = regression_measurements(actual, predictions.ravel())
    dummy_metrics = regression_measurements(actual, dummy_predictions.ravel())
    regression_codes = score_codes(predictions.ravel()).reshape(predictions.shape)
    comparison = None
    classifier_metrics = None
    if classifier_codes is not None:
        comparison = clustered_comparison(
            classifier_codes == strata[:, None], regression_codes == strata[:, None]
        )
        classifier_metrics = measurements(
            np.repeat(strata, OUTER_REPEATS), classifier_codes.ravel()
        )
        classifier_metrics.pop("accuracy_wilson_95_interval")
    indices = np.random.default_rng(EVALUATION_SEED).integers(0, len(y), size=(10000, len(y)))
    error_by_stock = np.abs(predictions - y[:, None]).mean(axis=1)
    metrics["mae_stock_bootstrap_95_interval"] = np.quantile(
        error_by_stock[indices].mean(axis=1), [0.025, 0.975]
    ).tolist()
    print("Outer evaluation complete; selecting and refitting the final regressor", flush=True)
    final_cv = RepeatedStratifiedKFold(n_splits=3, n_repeats=2, random_state=EVALUATION_SEED)
    final_splits = list(final_cv.split(frame, strata))
    final_search = search_factory(workers, final_splits).fit(frame, y)
    pipeline = final_search.best_estimator_
    bundle = {
        "task": "score_regression",
        "target": "Fundamental_Score",
        "target_origin": "Contextual financial policy on cleaned evidence",
        "selection_metric": selection_metric,
        "pipeline": pipeline,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "input_features": list(frame),
        "contextual_features": True,
        "extended_features": True,
        "score_bands": SCORE_BANDS,
        "score_decimals": SCORE_DECIMALS,
        "seed": EVALUATION_SEED,
        "sklearn_version": sklearn.__version__,
        "snapshot_date": rows[0]["Snapshot_Date"],
        "source_csv_sha256": sha256(csv_path),
        "source_raw_sha256": sha256(raw_path),
        "model_role": "Predict score, then apply fixed bands; rule scores retained for comparison",
    }
    joblib.dump(bundle, output / "model.joblib")
    reloaded = joblib.load(output / "model.joblib")
    np.testing.assert_array_equal(pipeline.predict(frame), reloaded["pipeline"].predict(frame))
    (output / "stock_predictions.json").write_text(
        json.dumps(predict_rows(reloaded, rows), indent=2, allow_nan=False)
    )
    oof = [
        {
            "Symbol": row["Symbol"],
            "Actual_Score": float(y[i]),
            "Actual_Label": row["Fundamental"],
            "Predicted_Scores": predictions[i].tolist(),
            "Predicted_Labels": [CLASSES[int(c)] for c in regression_codes[i]],
            "Classifier_Codes": classifier_codes[i].tolist()
            if classifier_codes is not None
            else None,
        }
        for i, row in enumerate(eligible)
    ]
    (output / "out_of_fold_predictions.json").write_text(json.dumps(oof, indent=2))
    transformed = pipeline.named_steps["features"].transform(frame)
    encoded = pipeline.named_steps["preprocess"].transform(transformed)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "task": "score_regression",
        "target": "Fundamental_Score",
        "snapshot_date": rows[0]["Snapshot_Date"],
        "total_stocks": len(rows),
        "assessable_stocks": len(y),
        "limited_stocks": len(rows) - len(y),
        "class_counts": dict(Counter(r["Fundamental"] for r in rows)),
        "target_range": [float(y.min()), float(y.max())],
        "evaluation": "Five-fold nested CV, two repeats; stratified by fixed score bands",
        "selection_metric": selection_metric,
        "unique_stocks": len(y),
        "validation_appearances": len(actual),
        "outer_seed": EVALUATION_SEED,
        "nested_cv": metrics,
        "median_score_baseline": dummy_metrics,
        "previous_classifier_same_folds": classifier_metrics,
        "derived_label_comparison": comparison,
        "folds": folds,
        "selected_model": type(pipeline.named_steps["regressor"]).__name__,
        "final_parameters": parameters(final_search.best_params_),
        "full_regressor_parameters": parameter_value(pipeline.named_steps["regressor"]),
        "final_selection_cv_mae_points": -float(
            final_search.cv_results_["mean_test_neg_mae"][final_search.best_index_]
        ),
        "final_selection_cv_band_accuracy": float(
            final_search.cv_results_["mean_test_band_accuracy"][final_search.best_index_]
        ),
        "configuration_count": len(ParameterGrid(final_search.param_grid)),
        "candidates": [
            {
                "parameters": parameters(params),
                "cv_mae_points": -float(final_search.cv_results_["mean_test_neg_mae"][i]),
                "cv_rmse_points": -float(final_search.cv_results_["mean_test_neg_rmse"][i]),
                "cv_r2": float(final_search.cv_results_["mean_test_r2"][i]),
                "cv_band_accuracy": float(final_search.cv_results_["mean_test_band_accuracy"][i]),
            }
            for i, params in enumerate(final_search.cv_results_["params"])
        ],
        "input_features": list(frame),
        "financial_feature_count": transformed.shape[1],
        "encoded_feature_count": encoded.shape[1],
        "score_bands": SCORE_BANDS,
        "score_decimals": SCORE_DECIMALS,
        "data_audit": audit,
        "model_sha256": sha256(output / "model.joblib"),
        "comparison_report_sha256": (
            sha256(comparison_dir / "improvement_report.json") if comparison_dir else None
        ),
        "comparison_oof_sha256": (
            sha256(comparison_dir / "out_of_fold_predictions.json") if comparison_dir else None
        ),
        "limitations": [
            "Target scores are rule-generated, not independent audited financial-quality scores",
            "Previously examined single snapshot; no new external test or future accuracy",
            "All model and feature selection occurs inside outer training folds",
            "312 validation appearances represent 156 unique stocks, each evaluated twice",
            "Stock bootstrap intervals are descriptive; CV fits are dependent",
            "Seven stocks in each weak band; inspect minority-label recall separately",
            "Regression can smooth severe rule risks or cross label boundaries",
            "Final refit predictions are in-sample and are not validation accuracy",
            "Limited Assessment is gated, never assigned an imputed target score",
            "Score estimates are not probabilities or return forecasts",
        ],
    }
    if previous_regression is not None:
        previous_report = json.loads((previous_regression / "regression_report.json").read_text())
        previous_splits = json.loads((previous_regression / "outer_splits.json").read_text())
        previous_oof = json.loads(
            (previous_regression / "out_of_fold_predictions.json").read_text()
        )
        if (
            previous_splits != manifest
            or previous_report["data_audit"]["raw_sha256"] != audit["raw_sha256"]
        ):
            raise ValueError("Previous score regression uses different folds or observations")
        if [r["Symbol"] for r in previous_oof] != [r["Symbol"] for r in eligible] or any(
            r["Actual_Score"] != float(y[i]) for i, r in enumerate(previous_oof)
        ):
            raise ValueError("Previous score regression target/universe differs")
        previous_scores = np.array([r["Predicted_Scores"] for r in previous_oof])
        if previous_scores.shape != predictions.shape:
            raise ValueError("Previous score regression validation predictions incomplete")
        previous_metrics = regression_measurements(actual, previous_scores.ravel())
        previous_codes = score_codes(previous_scores.ravel()).reshape(predictions.shape)
        report["previous_regression_same_folds"] = previous_metrics
        report["regression_label_comparison"] = clustered_comparison(
            previous_codes == strata[:, None], regression_codes == strata[:, None]
        )
        report["previous_regression_report_sha256"] = sha256(
            previous_regression / "regression_report.json"
        )
        report["improved_category_accuracy"] = (
            metrics["derived_labels"]["accuracy"] > previous_metrics["derived_labels"]["accuracy"]
        )
        report["score_mae_change_points"] = metrics["mae_points"] - previous_metrics["mae_points"]
    report["search_factory"] = search_factory.__name__
    (output / "regression_report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    print(
        json.dumps(
            {
                "model": report["selected_model"],
                "mae_points": metrics["mae_points"],
                "rmse_points": metrics["rmse_points"],
                "r2": metrics["r2"],
                "derived_label_accuracy": metrics["derived_labels"]["accuracy"],
                "output": str(output),
            },
            indent=2,
        ),
        flush=True,
    )
    return report


def activate_regression(output: Path) -> None:
    """Activate only a completed, checksum-verified score model; retain the previous pointer."""
    from backend.app.fundamentals.publication import (
        ACTIVE_MODEL_POINTER,
        DEFAULT_PUBLICATION,
        ROOT,
        atomic_json,
        run_lock,
    )

    model = (output / "model.joblib").resolve()
    if not model.is_relative_to((ROOT / "data/models/fundamentals").resolve()):
        raise ValueError("Active model must be inside the fundamentals model directory")
    report = json.loads((output / "regression_report.json").read_text())
    if sha256(model) != report["model_sha256"]:
        raise ValueError("Regression model checksum differs from completed report")
    bundle = joblib.load(model)
    if (
        bundle.get("task") != "score_regression"
        or bundle.get("target") != "Fundamental_Score"
        or bundle.get("sklearn_version") != sklearn.__version__
    ):
        raise ValueError("Completed model is not a compatible score regressor")
    with run_lock(DEFAULT_PUBLICATION):
        if ACTIVE_MODEL_POINTER.exists():
            atomic_json(
                output / "previous_active_model.json", json.loads(ACTIVE_MODEL_POINTER.read_text())
            )
        atomic_json(
            ACTIVE_MODEL_POINTER,
            {
                "path": str(model.relative_to(ROOT)),
                "sha256": report["model_sha256"],
                "evaluation_report": str(
                    (output / "regression_report.json").resolve().relative_to(ROOT)
                ),
                "task": "score_regression",
                "target": "Fundamental_Score",
                "role": "Predicted score determines label; rules retained for comparison",
                "nested_cv_mae_points": report["nested_cv"]["mae_points"],
                "derived_label_cv_accuracy": report["nested_cv"]["derived_labels"]["accuracy"],
            },
        )
