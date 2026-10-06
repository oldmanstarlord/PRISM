"""Evaluate a broad score-regression parameter search against the current model."""

import argparse
import json
from pathlib import Path

from sklearn.model_selection import ParameterGrid

from backend.app.fundamentals.data import sha256
from backend.app.fundamentals.publication import ACTIVE_MODEL_POINTER
from backend.app.fundamentals.regression import activate_regression, train_regression
from backend.app.fundamentals.regression_improvement import complete_search_metadata
from backend.app.fundamentals.regression_tuning import (
    broad_regression_search,
    configuration_definition,
)
from backend.app.fundamentals.training import SEED


def write_search_plan(output: Path, csv_path: Path, raw_path: Path) -> None:
    """Persist the complete data-independent search before seeing validation results."""
    if (output / "model.joblib").exists() or (output / "regression_report.json").exists():
        raise ValueError("Use a new output directory; cannot overwrite a completed experiment")
    search = broad_regression_search(1, [])
    configurations = [
        configuration_definition(search.estimator, params)
        for params in ParameterGrid(search.param_grid)
    ]
    plan = {
        "target": "Fundamental_Score",
        "core_exhaustive_combinations": 432,
        "total_unique_configurations": len(configurations),
        "fixed_sampling_seed": SEED,
        "method": "Exhaustive core ranges plus fixed sampled broader ranges; "
        "retain all previous 112 candidates",
        "csv_sha256": sha256(csv_path),
        "raw_sha256": sha256(raw_path),
        "active_pointer_before_training": json.loads(ACTIVE_MODEL_POINTER.read_text())
        if ACTIVE_MODEL_POINTER.exists()
        else None,
        "configurations": configurations,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "search_plan.json").write_text(json.dumps(plan, indent=2, allow_nan=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/processed/fundamentals/nifty200_fundamentals_2026-10-05.csv"),
    )
    parser.add_argument(
        "--raw", type=Path, default=Path("data/raw/fundamentals/2026-10-05/parsed_snapshot.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/models/fundamentals/2026-10-05-regression-broad"),
    )
    parser.add_argument(
        "--previous",
        type=Path,
        default=Path("data/models/fundamentals/2026-10-05-regression-improved"),
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    write_search_plan(args.output, args.csv, args.raw)
    report = train_regression(
        args.csv,
        args.raw,
        args.output,
        workers=args.workers,
        search_factory=broad_regression_search,
        selection_metric="Highest inner-CV derived-category accuracy; score MAE breaks ties",
        previous_regression=args.previous,
    )
    complete_search_metadata(args.output, args.csv, args.raw, broad_regression_search)
    if args.activate:
        old = report["previous_regression_same_folds"]
        new = report["nested_cv"]
        if not report["improved_category_accuracy"] or new["mae_points"] > old["mae_points"]:
            print("No joint accuracy/score-error improvement; current active model retained")
        else:
            activate_regression(args.output)


if __name__ == "__main__":
    main()
