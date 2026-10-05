"""Job to ingest benchmark index historical series idempotently (FR-D8, D6, Task 4)."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from backend.app.correlation_mst.service import _canonical_hash
from backend.app.db.models import PipelineRun
from backend.app.db.session import SessionLocal
from backend.app.market_data.benchmark import (
    BenchmarkPriceRecord,
    CsvBenchmarkAdapter,
    YahooBenchmarkAdapter,
    persist_benchmark_series,
)
from backend.app.market_data.benchmark_check import run_benchmark_checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["yahoo", "csv"],
        default="yahoo",
        help="Benchmark source (default: yahoo)",
    )
    parser.add_argument(
        "--symbol",
        default="^CNX200",
        help="Benchmark symbol (default: ^CNX200)",
    )
    parser.add_argument(
        "--benchmark-id",
        default="NIFTY_200",
        help="Benchmark ID (default: NIFTY_200)",
    )
    parser.add_argument(
        "--csv-file",
        type=Path,
        help="Path to index CSV file (required for csv source)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist validated benchmark series to database (default: dry-run)",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)

    # 1. Fetch benchmark records strictly from requested source (no sample data fallback)
    records: list[BenchmarkPriceRecord] = []
    source_tag: str

    if args.source == "yahoo":
        source_tag = "YAHOO"
        adapter = YahooBenchmarkAdapter(symbol=args.symbol)
        try:
            records = adapter.fetch_series(benchmark_id=args.benchmark_id)
        except Exception as exc:
            sys.exit(f"Failed to fetch benchmark from Yahoo Finance ({args.symbol}): {exc}")
    elif args.source == "csv":
        source_tag = "CSV"
        if not args.csv_file:
            sys.exit("Error: --csv-file is required for CSV mode. No sample fallback allowed.")
        if not args.csv_file.exists():
            sys.exit(f"Error: CSV file not found: {args.csv_file}")
        csv_text = args.csv_file.read_text(encoding="utf-8")
        csv_adapter = CsvBenchmarkAdapter()
        try:
            records = csv_adapter.parse_csv(csv_text)
        except Exception as exc:
            sys.exit(f"Failed to parse CSV benchmark file: {exc}")
    else:
        sys.exit(f"Unsupported source: {args.source}")

    if not records:
        sys.exit("Error: No benchmark records retrieved from source. Exiting with zero writes.")

    # 2. Run consistency checks and PASS RULES
    session = None
    try:
        from sqlalchemy import create_engine

        from backend.app.core.config import settings

        test_engine = create_engine(
            settings.database_url,
            connect_args={"connect_timeout": 2},
        )
        with test_engine.connect():
            pass
        session = SessionLocal()
    except Exception as exc:
        print(f"Note: Database unavailable ({exc}); proceeding without database alignment data.")
        session = None

    try:
        report = run_benchmark_checks(
            records=records,
            session=session,
            source=source_tag,
            symbol=args.symbol,
        )

        # Print consistency report to console
        markdown_report = report.render_markdown()
        print(markdown_report)

        # Write consistency report to docs/evidence/benchmark_check.md
        evidence_dir = Path("docs/evidence")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_file = evidence_dir / "benchmark_check.md"
        evidence_file.write_text(markdown_report, encoding="utf-8")
        print(f"\nReport written to: {evidence_file}")

        # Check if dry-run
        if not args.apply:
            print(
                "\n[DRY-RUN] Benchmark data was verified and checked. "
                "No changes written to database. Use --apply to persist."
            )
            return

        if session is None:
            sys.exit("Error: Database connection is not available. Cannot persist with --apply.")

        # Enforce PASS RULES before writing
        if not report.all_pass:
            failed_rules = [r.rule_name for r in report.rule_evaluations if not r.passed]
            rules_str = ", ".join(failed_rules)
            reason_str = report.stop_reason or "Validation failure"
            print(
                f"\n[ERROR] Cannot persist benchmark: PASS RULES failed ({rules_str}).\n"
                f"Stop condition: {reason_str}. Writing nothing.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Persist benchmark series
        inserted, issues = persist_benchmark_series(
            session=session,
            benchmark_id=args.benchmark_id,
            records=records,
            source=source_tag,
        )

        completed_at = datetime.now(UTC)
        run = PipelineRun(
            workflow="ingest_benchmark",
            code_version="1.0.0",
            configuration_hash=_canonical_hash(
                {
                    "source": source_tag,
                    "symbol": args.symbol,
                    "benchmark_id": args.benchmark_id,
                }
            ),
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts={
                "fetched_records": len(records),
                "inserted_records": inserted,
                "first_date": str(report.first_date),
                "last_date": str(report.last_date),
            },
            quality_summary={
                "issues_count": len(issues),
                "all_pass": report.all_pass,
                "overall_correlation": report.overall_correlation,
                "duplicate_count": report.duplicate_count,
            },
        )
        session.add(run)
        session.commit()

        print(
            f"\n[APPLIED] Ingested {args.benchmark_id}: {len(records)} fetched, "
            f"{inserted} inserted, {len(issues)} issues."
        )
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    main()
