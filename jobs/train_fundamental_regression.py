"""Train score regressors and evaluate categories derived from their predictions."""

import argparse
from pathlib import Path

from backend.app.fundamentals.regression import activate_regression, train_regression


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
        "--output", type=Path, default=Path("data/models/fundamentals/2026-10-05-regression")
    )
    parser.add_argument(
        "--comparison", type=Path, default=Path("data/models/fundamentals/2026-10-05-improved")
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--no-comparison",
        action="store_true",
        help="Train without an earlier classifier comparison",
    )
    parser.add_argument("--activate", action="store_true", help="Activate after training completes")
    args = parser.parse_args()
    comparison = None if args.no_comparison else args.comparison
    train_regression(args.csv, args.raw, args.output, comparison, args.workers)
    if args.activate:
        activate_regression(args.output)


if __name__ == "__main__":
    main()
