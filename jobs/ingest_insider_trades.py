"""Incremental, idempotent insider trade ingestion job.

Usage:
  uv run python jobs/ingest_insider_trades.py --file data/insider_trades.csv
  uv run python jobs/ingest_insider_trades.py --symbol INFY --file data/infy_insider.csv

Source access:
  NSE/BSE do not provide an authenticated public API (see ASSUMPTION PD-8).
  Operator downloads CSV from nseindia.com → Corporate Filings → Insider Trading
  (SEBI PIT Reg 7(2)) or SAST Regulation pages and places it in data/ directory.

CSV format (required columns):
  symbol, person_category, txn_type, quantity, value, txn_date,
  published_at[, source_doc_id]

txn_type must be one of: buy, sell, pledge, revoke_pledge
published_at must be the actual exchange acceptance date — never estimated.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.data_sources.service import mark_source_success
from backend.app.db.session import get_session
from backend.app.governance.adapters.csv_adapter import CsvInsiderTradeAdapter
from backend.app.governance.service import (
    _resolve_security,
    ingest_insider_trade_records,
)


def run(file_path: str, symbol: str | None = None) -> None:
    adapter = CsvInsiderTradeAdapter(file_path=file_path)
    now_utc = datetime.now(UTC)

    with next(get_session()) as session:
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

            docs = adapter.fetch_trades(sym, as_of=now_utc)
            for doc in docs:
                counts = ingest_insider_trade_records(
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

        mark_source_success(
            session,
            "insider_trades_nse_manual",
            succeeded_at=now_utc,
            verified=True,
        )
        session.commit()
        print(
            f"\nDone. inserted={total_inserted} skipped={total_skipped} not_found={total_not_found}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest insider trades from CSV.")
    parser.add_argument("--file", required=True, help="Path to insider trades CSV file")
    parser.add_argument(
        "--symbol",
        default=None,
        help="Only ingest this symbol (optional)",
    )
    args = parser.parse_args()
    run(file_path=args.file, symbol=args.symbol)


if __name__ == "__main__":
    main()
