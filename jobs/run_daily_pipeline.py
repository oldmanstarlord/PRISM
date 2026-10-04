"""Run the fail-closed daily PRISM ingestion and analysis workflow."""

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.pipeline.service import run_daily_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2015, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Publish from the latest stored validated snapshot without calling the provider",
    )
    args = parser.parse_args()
    with SessionLocal() as session:
        result = run_daily_pipeline(
            session,
            start=args.start,
            end=args.end,
            snapshot_root=Path("data/raw/yfinance"),
            max_workers=args.workers,
            skip_ingestion=args.skip_ingestion,
        )
    print(json.dumps(asdict(result), default=str, indent=2, sort_keys=True))
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
