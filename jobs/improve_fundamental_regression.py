"""Improve category accuracy using numeric score regression and unchanged score bands."""

import argparse
from pathlib import Path

from backend.app.fundamentals.regression import activate_regression, train_regression
from backend.app.fundamentals.regression_improvement import (
    complete_search_metadata,
    improved_regression_search,
)


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
        default=Path("data/models/fundamentals/2026-10-05-regression-improved"),
    )
    parser.add_argument(
        "--comparison", type=Path, default=Path("data/models/fundamentals/2026-10-05-improved")
    )
    parser.add_argument(
        "--previous", type=Path, default=Path("data/models/fundamentals/2026-10-05-regression")
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    report = train_regression(
        args.csv,
        args.raw,
        args.output,
        args.comparison,
        args.workers,
        search_factory=improved_regression_search,
        selection_metric="Highest inner-CV derived-category accuracy; score MAE breaks ties",
        previous_regression=args.previous,
    )
    complete_search_metadata(args.output, args.csv, args.raw)
    if args.activate:
        if not report["improved_category_accuracy"]:
            raise ValueError("Category accuracy did not improve; previous active model retained")
        activate_regression(args.output)


if __name__ == "__main__":
    main()
