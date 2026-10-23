"""Create frozen weekly heterogeneous graph snapshots from stored PRISM data."""

import argparse
from datetime import date
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.gnn.config import GraphConfig
from backend.app.gnn.dataset import load_from_database, save_dataset, split_indices


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--research-fixed-universe",
        action="store_true",
        help="Use currently known membership/revisions retrospectively; not point-in-time",
    )
    parser.add_argument("--min-stocks", type=int, default=20)
    parser.add_argument("--lookback-days", type=int, default=121)
    args = parser.parse_args()
    config = GraphConfig(min_stocks=args.min_stocks, lookback_days=args.lookback_days)
    with SessionLocal() as session:
        dataset = load_from_database(
            session,
            args.start,
            args.end,
            config,
            research_fixed_universe=args.research_fixed_universe,
        )
    splits = split_indices(len(dataset.snapshots), config)
    save_dataset(dataset, args.output)
    print(
        f"Saved {len(dataset.snapshots)} snapshots, {len(dataset.symbols)} stocks to {args.output}"
    )
    print(f"Universe mode: {dataset.universe_mode}; fingerprint: {dataset.fingerprint}")
    print(
        "Split counts: " + ", ".join(f"{name}={len(indices)}" for name, indices in splits.items())
    )


if __name__ == "__main__":
    main()
