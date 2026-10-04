"""Command-line entry point for incremental NIFTY 200 daily price ingestion."""

import argparse
import json
from datetime import date
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.market_data.service import ingest_nifty200_prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NIFTY 200 daily market data")
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=date(2015, 1, 1),
        help="Earliest date for securities without stored history (default: 2015-01-01)",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=date.today(),
        help="Final date to request, inclusive (default: today)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrent Yahoo downloads; database writes remain sequential (default: 8)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Optional NSE symbols for targeted recovery; default processes the full universe",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        summary = ingest_nifty200_prices(
            session,
            start=args.start,
            end=args.end,
            snapshot_root=Path("data/raw/yfinance"),
            max_workers=args.workers,
            symbols=set(args.symbols) if args.symbols else None,
        )
    print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
