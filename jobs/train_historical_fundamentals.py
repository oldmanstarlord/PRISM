"""Run the declared exhaustive grids and blends with a later-period holdout."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.fundamentals.historical_regression import train
from jobs.build_fundamentals import ROOT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panel",
        type=Path,
        default=(
            ROOT
            / "data/processed/fundamentals/history-yahoo-2026-10-06-duration-verified"
            / "historical_panel.json"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/models/fundamentals/2026-10-06-historical-blend"
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    train(args.panel.resolve(), args.output.resolve(), args.workers)
