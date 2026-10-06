"""Forward-period model search and continuous-score ensembles for historical panels."""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
from joblib import Parallel, delayed
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.model_selection import ParameterGrid
from sklearn.pipeline import Pipeline
from sklearn.svm import SVR
from xgboost import XGBRegressor

from backend.app.fundamentals.data import (
    LIMITED,
    POLICY_VERSION,
    SCHEMA_VERSION,
    feature_frame,
    sha256,
)
from backend.app.fundamentals.estimators import FinancialInteractions
from backend.app.fundamentals.regression import (
    parameter_value,
    regression_measurements,
    regression_search,
)
from backend.app.fundamentals.score_estimators import CatBoostScoreRegressor, TreeScoreRegressor
from backend.app.fundamentals.scores import bounded_scores, score_codes
from backend.app.fundamentals.training import SEED


class ScoreBlendRegressor(RegressorMixin, BaseEstimator):  # type: ignore[misc]
    """Blend numeric score predictions; labels are derived only after regression."""

    def __init__(
        self,
        estimators: list[tuple[str, Any]],
        weights: list[float] | None = None,
        aggregation: str = "mean",
    ) -> None:
        self.estimators = estimators
        self.weights = weights
        self.aggregation = aggregation

    def fit(self, X: Any, y: Any) -> ScoreBlendRegressor:
        if self.aggregation not in {"mean", "median"}:
            raise ValueError("Unsupported score aggregation")
        self.estimators_ = [(name, clone(model).fit(X, y)) for name, model in self.estimators]
        self.weights_ = np.asarray(
            self.weights if self.weights is not None else [1.0] * len(self.estimators), dtype=float
        )
        if (
            self.weights_.shape != (len(self.estimators),)
            or not np.isfinite(self.weights_).all()
            or (self.weights_ < 0).any()
            or self.weights_.sum() <= 0
        ):
            raise ValueError("Blend weights must be finite, nonnegative and sum positive")
        return self

    def predict(self, X: Any) -> np.ndarray:
        predictions = np.column_stack([model.predict(X) for _, model in self.estimators_])
        return (
            np.median(predictions, axis=1)
            if self.aggregation == "median"
            else np.average(predictions, axis=1, weights=self.weights_)
        )


def candidates() -> list[dict[str, Any]]:
    families = []
    for name, constructor in [
        ("ExtraTrees", ExtraTreesRegressor),
        ("RandomForest", RandomForestRegressor),
    ]:
        model = TreeScoreRegressor(constructor(n_jobs=1, random_state=SEED))
        families.append(
            (
                name,
                model,
                {
                    "estimator__n_estimators": [220, 400],
                    "estimator__max_features": [0.6, 1.0],
                    "estimator__max_depth": [None, 12],
                    "estimator__min_samples_leaf": [1, 3],
                    "estimator__min_samples_split": [2, 8],
                    "estimator__bootstrap": [False, True],
                    "aggregation": ["mean", "median"],
                },
            )
        )
    families.extend(
        [
            (
                "HistGradientBoosting",
                HistGradientBoostingRegressor(random_state=SEED),
                {
                    "max_iter": [180, 350],
                    "max_leaf_nodes": [7, 15, 31],
                    "min_samples_leaf": [3, 8],
                    "learning_rate": [0.04, 0.1],
                    "l2_regularization": [1, 5],
                },
            ),
            (
                "XGBoost",
                XGBRegressor(
                    n_jobs=1, random_state=SEED, objective="reg:squarederror", tree_method="hist"
                ),
                {
                    "n_estimators": [180, 350],
                    "max_depth": [2, 3, 5],
                    "learning_rate": [0.03, 0.1],
                    "reg_lambda": [1, 5],
                    "subsample": [0.8, 1.0],
                    "colsample_bytree": [0.8, 1.0],
                    "min_child_weight": [1, 3],
                },
            ),
            (
                "CatBoost",
                CatBoostScoreRegressor(),
                {
                    "depth": [3, 5, 7],
                    "iterations": [350, 600],
                    "learning_rate": [0.04, 0.1],
                    "loss": ["RMSE", "MAE"],
                    "l2": [1, 5],
                },
            ),
            ("Ridge", Ridge(), {"alpha": [0.01, 0.1, 1, 10, 100, 1000]}),
            ("SVR", SVR(), {"C": [10, 100, 1000], "epsilon": [0.1, 1], "gamma": ["scale", 0.01]}),
        ]
    )
    results: list[dict[str, Any]] = []
    for view in ["compact", "rich"]:
        for name, model, grid in families:
            for settings in ParameterGrid(grid):
                fitted_model = clone(model).set_params(**settings)
                results.append(
                    {
                        "index": len(results),
                        "family": name,
                        "view": view,
                        "model": fitted_model,
                        "definition": parameter_value(fitted_model),
                    }
                )
    return results


def forward_splits(
    dates: np.ndarray, validation_dates: list[str], minimum_training: int = 100
) -> list[tuple[np.ndarray, np.ndarray]]:
    splits = []
    for period in validation_dates:
        train, validation = np.flatnonzero(dates < period), np.flatnonzero(dates == period)
        if len(train) < minimum_training or not len(validation):
            raise ValueError(f"Insufficient history for temporal fold {period}")
        if max(dates[train]) >= min(dates[validation]):
            raise AssertionError("Temporal split leaks future periods")
        splits.append((train, validation))
    return splits


def preference(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float]:
    bounded = bounded_scores(predicted)
    return float(np.mean(score_codes(actual) == score_codes(bounded))), -float(
        np.mean(abs(actual - bounded))
    )


def simplex_weights(count: int, units: int = 10) -> Any:
    """Every nonnegative weight vector on the declared 0.1 grid, summing to one."""
    for bars in itertools.combinations(range(units + count - 1), count - 1):
        limits = (-1, *bars, units + count - 1)
        yield [float(limits[i + 1] - limits[i] - 1) / units for i in range(count)]


def blend_search(
    actual: np.ndarray, predictions: np.ndarray
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    count = predictions.shape[1]
    trials, winner = [], None
    best = (-1.0, -float("inf"))
    for weights in simplex_weights(count):
        predicted = np.average(predictions, axis=1, weights=weights)
        accuracy, negative_mae = preference(actual, predicted)
        trial = {
            "aggregation": "mean",
            "weights": weights,
            "accuracy": accuracy,
            "mae": -negative_mae,
        }
        trials.append(trial)
        if (accuracy, negative_mae) > best:
            best, winner = (accuracy, negative_mae), trial
    # Also test every nonempty subset's equal-weight mean and robust median.
    for size in range(1, count + 1):
        for subset in itertools.combinations(range(count), size):
            for aggregation in ["mean", "median"]:
                predicted = (np.mean if aggregation == "mean" else np.median)(
                    predictions[:, subset], axis=1
                )
                accuracy, negative_mae = preference(actual, predicted)
                trial = {
                    "aggregation": aggregation,
                    "weights": [float(i in subset) / size for i in range(count)],
                    "accuracy": accuracy,
                    "mae": -negative_mae,
                }
                trials.append(trial)
                if (accuracy, negative_mae) > best:
                    best, winner = (accuracy, negative_mae), trial
    assert winner is not None
    return winner, trials


def pipeline(model: Any, view: str) -> Pipeline:
    preprocess = clone(regression_search(1, []).estimator.named_steps["preprocess"])
    return Pipeline(
        [
            ("features", FinancialInteractions(view=view)),
            ("preprocess", preprocess),
            ("regressor", clone(model)),
        ]
    )


def fit_candidate(
    candidate: dict[str, Any],
    encoded: dict[str, Any],
    targets: np.ndarray,
    splits: list[tuple[np.ndarray, np.ndarray]],
    cache: Path,
    partner: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = cache / f"{candidate['index']:04d}.json"
    if path.exists():
        return cast(dict[str, Any], json.loads(path.read_text()))
    if partner and (cache / f"{partner['index']:04d}.json").exists():
        partner = None
    predictions, actual, fold_results = [], [], []
    partner_predictions: list[float] = []
    partner_folds = []
    for (train, validation), (train_x, valid_x) in zip(
        splits, encoded[candidate["view"]], strict=True
    ):
        model = clone(candidate["model"]).fit(train_x, targets[train])
        pred = np.asarray(model.predict(valid_x), dtype=float)
        predictions.extend(pred.tolist())
        actual.extend(targets[validation].tolist())
        accuracy, negative_mae = preference(targets[validation], pred)
        fold_results.append({"accuracy": accuracy, "mae": -negative_mae})
        if partner:
            # Aggregation is applied after fitting; both candidates use identical
            # fitted trees and the same validation rows, without duplicate fits.
            model.aggregation = partner["model"].aggregation
            alternate = np.asarray(model.predict(valid_x), dtype=float)
            partner_predictions.extend(alternate.tolist())
            accuracy, negative_mae = preference(targets[validation], alternate)
            partner_folds.append({"accuracy": accuracy, "mae": -negative_mae})
    accuracy, negative_mae = preference(np.asarray(actual), np.asarray(predictions))
    result = {
        "index": candidate["index"],
        "family": candidate["family"],
        "view": candidate["view"],
        "definition": candidate["definition"],
        "accuracy": accuracy,
        "mae": -negative_mae,
        "folds": fold_results,
        "predictions": predictions,
    }
    path.write_text(json.dumps(result, allow_nan=False))
    if partner:
        accuracy, negative_mae = preference(np.asarray(actual), np.asarray(partner_predictions))
        other = {
            **result,
            "index": partner["index"],
            "definition": partner["definition"],
            "accuracy": accuracy,
            "mae": -negative_mae,
            "folds": partner_folds,
            "predictions": partner_predictions,
            "tree_fit_shared_with": candidate["index"],
        }
        (cache / f"{partner['index']:04d}.json").write_text(json.dumps(other, allow_nan=False))
    return result


def train(panel_path: Path, output: Path, workers: int = 4) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if (output / "model.joblib").exists():
        raise ValueError("Completed historical model output already exists")
    all_rows = json.loads(panel_path.read_text())
    rows = [r for r in all_rows if r["Fundamental"] != LIMITED and r["Training_State_Changed"]]
    frame = feature_frame(rows, contextual=True, extended=True)
    targets = np.array([r["Fundamental_Score"] for r in rows], dtype=float)
    dates = np.array([r["Snapshot_Date"] for r in rows])
    held_period = "2026-09-30"
    development = np.flatnonzero(dates < held_period)
    holdout = np.flatnonzero(dates == held_period)
    if not len(holdout) or not len(development):
        raise ValueError("Missing development or holdout cohort")
    development_dates = dates[development]
    splits = forward_splits(
        development_dates, ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
    )
    grid = candidates()
    plan = {
        "panel_sha256": sha256(panel_path),
        "seed": SEED,
        "target": "Fundamental_Score",
        "selection": "Highest forward-validation category accuracy; score MAE breaks ties",
        "single_candidates": [{k: v for k, v in c.items() if k != "model"} for c in grid],
        "holdout_period": held_period,
        "folds": [
            {
                "train_rows": len(t),
                "validation_rows": len(v),
                "training_through": str(max(development_dates[t])),
                "validation_period": str(development_dates[v][0]),
            }
            for t, v in splits
        ],
        "blend_weight_grid": "All 0.1-step weights summing to 1 over seven family winners",
        "blend_subsets": "Every nonempty subset, equal mean and median",
        "development_rows": len(development),
        "holdout_rows": len(holdout),
    }
    encoded_plan = json.dumps(plan, sort_keys=True, allow_nan=False)
    plan_path = output / "search_plan.json"
    if (
        plan_path.exists()
        and hashlib.sha256(plan_path.read_text().encode()).hexdigest()
        != hashlib.sha256(encoded_plan.encode()).hexdigest()
    ):
        raise ValueError("Resume plan/source differs from original search")
    plan_path.write_text(encoded_plan)
    cache = output / "candidate_results"
    cache.mkdir(exist_ok=True)
    dev_x, dev_y = frame.iloc[development], targets[development]
    encoded: dict[str, Any] = {}
    for view in ["compact", "rich"]:
        encoded[view] = []
        for train_indices, valid_indices in splits:
            transformer = pipeline(Ridge(), view)[:-1]
            train_x = transformer.fit_transform(dev_x.iloc[train_indices], dev_y[train_indices])
            valid_x = transformer.transform(dev_x.iloc[valid_indices])
            encoded[view].append((train_x, valid_x))
    results = []
    tree_pairs: dict[str, dict[str, Any]] = {}
    partners: dict[int, dict[str, Any]] = {}
    for candidate in grid:
        if isinstance(candidate["model"], TreeScoreRegressor):
            identity = json.dumps(
                {"view": candidate["view"], "base": parameter_value(candidate["model"].estimator)},
                sort_keys=True,
            )
            if identity in tree_pairs:
                other = tree_pairs[identity]
                partners[candidate["index"]] = other
                partners[other["index"]] = candidate
            else:
                tree_pairs[identity] = candidate
    for start in range(0, len(grid), 12):
        batch = Parallel(n_jobs=workers)(
            delayed(fit_candidate)(c, encoded, dev_y, splits, cache, partners.get(c["index"]))
            for c in grid[start : start + 12]
        )
        results.extend(batch)
        (output / "progress.json").write_text(
            json.dumps({"completed": len(results), "total": len(grid)})
        )
        print(f"Temporal search {len(results)}/{len(grid)}", flush=True)
    winners = []
    for family in sorted({r["family"] for r in results}):
        winner = max(
            (r for r in results if r["family"] == family), key=lambda r: (r["accuracy"], -r["mae"])
        )
        winners.append(winner)
    validation_indices = np.concatenate([v for _, v in splits])
    actual = dev_y[validation_indices]
    best_blend, blend_trials = blend_search(
        actual, np.column_stack([r["predictions"] for r in winners])
    )
    selected_estimators, selected_weights = [], []
    for winner, weight in zip(winners, best_blend["weights"], strict=True):
        if weight > 0:
            definition = grid[winner["index"]]
            selected_estimators.append(
                (winner["family"], pipeline(definition["model"], definition["view"]))
            )
            selected_weights.append(weight)
    selected = ScoreBlendRegressor(selected_estimators, selected_weights, best_blend["aggregation"])
    # Lock all choices before ever predicting the later-period holdout.
    selected_definition = {
        "aggregation": best_blend["aggregation"],
        "members": [
            {"family": name, "weight": weight, "pipeline": parameter_value(model)}
            for (name, model), weight in zip(selected_estimators, selected_weights, strict=True)
        ],
    }
    (output / "locked_selection.json").write_text(
        json.dumps(selected_definition, indent=2, allow_nan=False)
    )
    selected.fit(dev_x, dev_y)
    holdout_predictions = bounded_scores(selected.predict(frame.iloc[holdout]))
    holdout_metrics = regression_measurements(targets[holdout], holdout_predictions)
    # Same historical training cohort and holdout for the old active configuration.
    baseline = pipeline(
        TreeScoreRegressor(
            ExtraTreesRegressor(
                n_estimators=220,
                max_features=1.0,
                max_depth=None,
                min_samples_leaf=1,
                min_samples_split=2,
                bootstrap=False,
                n_jobs=1,
                random_state=SEED,
            ),
            "median",
        ),
        "compact",
    )
    baseline.fit(dev_x, dev_y)
    baseline_metrics = regression_measurements(
        targets[holdout], baseline.predict(frame.iloc[holdout])
    )
    prior_period = max(str(d) for d in dates[development])
    previous = {
        r["Symbol"]: r["Fundamental_Score"]
        for r in all_rows
        if r["Snapshot_Date"] == prior_period and r["Fundamental"] != LIMITED
    }
    persistence_indices = [i for i in holdout if rows[i]["Symbol"] in previous]
    persistence = (
        regression_measurements(
            targets[persistence_indices],
            np.array([previous[rows[i]["Symbol"]] for i in persistence_indices]),
        )
        if persistence_indices
        else None
    )
    family_metrics = []
    for winner in winners:
        candidate = grid[winner["index"]]
        fitted = pipeline(candidate["model"], candidate["view"]).fit(dev_x, dev_y)
        family_metrics.append(
            {
                "family": winner["family"],
                "validation_accuracy": winner["accuracy"],
                "validation_mae": winner["mae"],
                "view": winner["view"],
                "definition": winner["definition"],
                "holdout": regression_measurements(
                    targets[holdout], fitted.predict(frame.iloc[holdout])
                ),
            }
        )
    predictions = [
        {
            "symbol": rows[i]["Symbol"],
            "date": held_period,
            "actual_score": float(targets[i]),
            "predicted_score": float(p),
            "actual_label": rows[i]["Fundamental"],
            "predicted_label": ["Very Weak", "Weak", "Moderate", "Strong", "Very Strong"][
                int(score_codes(np.asarray([p]))[0])
            ],
        }
        for i, p in zip(holdout, holdout_predictions, strict=True)
    ]
    (output / "holdout_predictions.json").write_text(json.dumps(predictions, indent=2))
    (output / "validation_predictions.json").write_text(
        json.dumps(
            {
                "row_indices": development[validation_indices].tolist(),
                "actual": actual.tolist(),
                "family_order": [r["family"] for r in winners],
                "predictions": [r["predictions"] for r in winners],
            },
            allow_nan=False,
        )
    )
    (output / "blend_results.json").write_text(json.dumps(blend_trials, allow_nan=False))
    report = {
        "target": "Fundamental_Score",
        "task": "score_regression",
        "seed": SEED,
        "single_configurations_tested": len(grid),
        "blend_configurations_tested": len(blend_trials),
        "candidate_validation_evaluations": len(grid) * len(splits),
        "recorded_base_fits": sum("tree_fit_shared_with" not in r for r in results) * len(splits),
        "development_rows": len(development),
        "holdout_rows": len(holdout),
        "eligible_rows": len(rows),
        "unique_eligible_companies": len({r["Symbol"] for r in rows}),
        "holdout_period": held_period,
        "validation_selection": best_blend,
        "holdout": holdout_metrics,
        "previous_configuration_same_data_holdout": baseline_metrics,
        "previous_score_persistence": {"rows": len(persistence_indices), "metrics": persistence},
        "best_parameters": selected_definition,
        "families": family_metrics,
        "label_counts": dict(Counter(r["Fundamental"] for r in rows)),
        "source_sha256": sha256(panel_path),
        "production_activated": False,
        "interpretation": (
            "Accuracy measures agreement with reconstructed score bands, not investment returns"
        ),
        "limitations": [
            "Historical statement vintages are restatement-prone; release dates assumed 90/60 days",
            "Current membership survivorship bias",
            "Same companies recur across periods",
            "One latest-period holdout is not an independent multi-year trading backtest",
            "Yahoo and Screener ratios differ; historical model remains separate from production",
        ],
    }
    (output / "regression_report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    # Save the evaluated pre-holdout model as well as the final all-history fit.
    metadata = {
        "task": "score_regression",
        "target": "Fundamental_Score",
        "policy_version": POLICY_VERSION,
        "schema_version": SCHEMA_VERSION,
        "contextual_features": True,
        "extended_features": True,
        "input_features": list(frame.columns),
        "source": "Yahoo_NSE_historical_reconstruction",
    }
    joblib.dump(
        {**metadata, "pipeline": selected},
        output / "evaluation_model.joblib",
    )
    final = clone(selected).fit(frame, targets)
    bundle = {
        **metadata,
        "pipeline": final,
        "report": report,
    }
    joblib.dump(bundle, output / "model.joblib")
    replay = joblib.load(output / "evaluation_model.joblib")["pipeline"]
    if not np.array_equal(bounded_scores(replay.predict(frame.iloc[holdout])), holdout_predictions):
        raise AssertionError("Reloaded holdout model predictions differ")
    print(
        json.dumps(
            {
                "holdout": holdout_metrics,
                "parameters": selected_definition,
                "single_configurations": len(grid),
                "blends": len(blend_trials),
            },
            indent=2,
        )
    )
