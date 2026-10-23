"""Evaluate GNN drift against transparent baselines and production gates."""

import argparse
import json
from pathlib import Path

from backend.app.gnn.dataset import read_dataset
from backend.app.gnn.evaluation import evaluate, read_experiment_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experiment-summary", type=Path)
    args = parser.parse_args()
    result = evaluate(
        read_dataset(args.dataset),
        args.analysis / "stock_drift.csv",
        experiment_summary=read_experiment_summary(args.experiment_summary),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
