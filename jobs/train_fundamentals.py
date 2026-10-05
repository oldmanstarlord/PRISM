"""Clean data, tune classifiers, evaluate once, and save a complete inference pipeline."""

import argparse
from pathlib import Path

from backend.app.fundamentals.training import train


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
    parser.add_argument("--output", type=Path, default=Path("data/models/fundamentals/2026-10-05"))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    train(args.csv, args.raw, args.output, args.workers)


if __name__ == "__main__":
    main()
