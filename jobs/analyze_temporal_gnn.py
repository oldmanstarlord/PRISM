"""Export descriptive per-stock and market embedding drift tables."""

import argparse
from pathlib import Path

from backend.app.gnn.analysis import analyze
from backend.app.gnn.dataset import read_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    args = parser.parse_args()
    print(analyze(read_dataset(args.dataset), args.run, args.output, device_name=args.device))


if __name__ == "__main__":
    main()
