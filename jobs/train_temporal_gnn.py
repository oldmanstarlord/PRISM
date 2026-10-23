"""Train the temporal heterogeneous GNN from a frozen graph dataset."""

import argparse
from pathlib import Path

from backend.app.gnn.dataset import read_dataset
from backend.app.gnn.training import TrainConfig, train


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = train(
        read_dataset(args.dataset),
        args.output,
        TrainConfig(epochs=args.epochs, patience=args.patience, seed=args.seed),
        device_name=args.device,
    )
    print(f"Test metrics: {report['test']}")


if __name__ == "__main__":
    main()
