"""Incremental, idempotent shareholding pattern ingestion job.

Usage:
  uv run python jobs/ingest_shareholding.py --file data/shareholding.csv
  uv run python jobs/ingest_shareholding.py --symbol RELIANCE --file data/reliance_sh.csv

Source access:
  NSE/BSE do not provide an authenticated public API (see ASSUMPTION PD-8).
  Operator downloads quarterly CSV from nseindia.com / bseindia.com and
  places it in the data/ directory for import.

CSV format (required columns):
  symbol, quarter_end, promoter_pct, promoter_pledged_pct_of_promoter,
  fii_pct, dii_pct, public_pct, published_at[, source_doc_id]

published_at must be the actual SEBI filing date — never estimated or assumed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.db.session import get_session
from backend.app.governance.adapters.csv_adapter import CsvShareholdingAdapter
from backend.app.governance.service import (
    _resolve_security,
    ingest_shareholding_records,
)


def run(file_path: str, symbol: str | None = None) -> None:
    adapter = CsvShareholdingAdapter(file_path=file_path)
    now_utc = datetime.now(UTC)

    with next(get_session()) as session:
        # Determine which symbols to ingest
        import csv

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            symbols_in_file: set[str] = {
                row["symbol"].strip().upper() for row in reader if row.get("symbol")
            }

        if symbol is not None:
            symbols_in_file = {symbol.strip().upper()} & symbols_in_file

        total_inserted = 0
        total_skipped = 0
        total_not_found = 0

        for sym in sorted(symbols_in_file):
            security = _resolve_security(session, sym)
            if security is None:
                print(f"  WARN: Symbol '{sym}' not found in security_alias — skipped.")
                total_not_found += 1
                continue

            docs = adapter.fetch_shareholding(sym, as_of=now_utc)
            for doc in docs:
                counts = ingest_shareholding_records(
                    session,
                    security_id=security.id,
                    records=doc.records,
                    ingested_at=now_utc,
                )
                total_inserted += counts["inserted"]
                total_skipped += counts["skipped_duplicate"]
                print(
                    f"  {sym}: inserted={counts['inserted']} "
                    f"skipped_duplicate={counts['skipped_duplicate']}"
                )

        session.commit()
        print(
            f"\nDone. inserted={total_inserted} skipped={total_skipped} not_found={total_not_found}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest shareholding patterns from CSV.")
    parser.add_argument("--file", required=True, help="Path to shareholding CSV file")
    parser.add_argument(
        "--symbol",
        default=None,
        help="Only ingest this symbol (optional; processes all symbols if omitted)",
    )
    args = parser.parse_args()
    run(file_path=args.file, symbol=args.symbol)


if __name__ == "__main__":
    main()
