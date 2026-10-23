"""Run reproducible multi-seed relation ablations for the temporal GNN."""

import argparse
import json
from pathlib import Path
from typing import Any, cast

import numpy as np

from backend.app.gnn.analysis import analyze
from backend.app.gnn.dataset import read_dataset
from backend.app.gnn.evaluation import evaluate
from backend.app.gnn.training import TrainConfig, train

EXPERIMENTS: dict[str, tuple[tuple[str, ...], tuple[int, ...]]] = {
    "full": ((), ()),
    "no_mst": (("mst",), ()),
    "no_correlation": (("correlated",), ()),
    "no_industry": (("industry",), ()),
    "no_market": (("market",), ()),
    "stock_only_graph": (("industry", "market"), ()),
    "non_graph_temporal": (("mst", "correlated", "industry", "market"), ()),
    "no_return_5d": ((), (0,)),
    "no_volatility_20d": ((), (1,)),
    "no_volume_change_20d": ((), (2,)),
    "no_drawdown_60d": ((), (3,)),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    dataset = read_dataset(args.dataset)
    rows: list[dict[str, object]] = []
    for name, (disabled_relations, disabled_features) in EXPERIMENTS.items():
        experiment_seeds = args.seeds if name == "full" else args.seeds[:1]
        for seed in experiment_seeds:
            run_dir = args.output / f"{name}_seed_{seed}"
            analysis_dir = args.output / f"{name}_seed_{seed}_analysis"
            report = train(
                dataset,
                run_dir,
                TrainConfig(
                    epochs=args.epochs,
                    seed=seed,
                    disabled_relations=disabled_relations,
                    disabled_stock_features=disabled_features,
                ),
                device_name=args.device,
            )
            analyze(dataset, run_dir, analysis_dir, device_name="cpu")
            validation = evaluate(dataset, analysis_dir / "stock_drift.csv")
            drift_methods = cast(dict[str, Any], validation["methods"])
            rows.append(
                {
                    "experiment": name,
                    "seed": seed,
                    "disabled_relations": disabled_relations,
                    "disabled_stock_features": disabled_features,
                    "test": report["test"],
                    "drift_evaluation": drift_methods["gnn"],
                }
            )
    full_aucs = []
    for row in rows:
        drift_evaluation = cast(dict[str, Any], row["drift_evaluation"])
        validation_metrics = cast(dict[str, Any], drift_evaluation["validation"])
        if row["experiment"] == "full" and validation_metrics["auc"] is not None:
            full_aucs.append(float(validation_metrics["auc"]))
    completed = {str(row["experiment"]) for row in rows}
    required_ablations_complete = set(EXPERIMENTS) <= completed
    seed_stable = len(full_aucs) == len(args.seeds) and float(np.std(full_aucs)) <= 0.03
    summary = {
        "dataset_fingerprint": dataset.fingerprint,
        "seeds": args.seeds,
        "epochs": args.epochs,
        "seed_stable": seed_stable,
        "full_auc_std": float(np.std(full_aucs)) if full_aucs else None,
        "required_ablations_complete": required_ablations_complete,
        "experiments": rows,
    }
    (args.output / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
