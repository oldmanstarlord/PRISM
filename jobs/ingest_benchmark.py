"""Job to ingest benchmark index historical series idempotently (FR-D8, D6)."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from backend.app.db.models import PipelineRun
from backend.app.db.session import SessionLocal
from backend.app.market_data.benchmark import CsvBenchmarkAdapter, persist_benchmark_series

SAMPLE_BENCHMARK_FIXTURE = """Date,Open,High,Low,Close,Volume
2026-09-25,12500.0,12580.0,12480.0,12550.0,150000000
2026-09-28,12560.0,12620.0,12540.0,12610.0,165000000
2026-09-29,12620.0,12650.0,12570.0,12590.0,140000000
2026-09-30,12600.0,12640.0,12580.0,12630.0,175000000
2026-10-01,12640.0,12710.0,12620.0,12690.0,190000000
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-file", type=Path, help="Path to index CSV file")
    parser.add_argument("--benchmark-id", default="NIFTY_200", help="Benchmark ID")
    parser.add_argument("--source", default="NIFTY_INDICES_CSV", help="Data source tag")
    args = parser.parse_args()

    started_at = datetime.now(UTC)

    if args.csv_file and args.csv_file.exists():
        csv_text = args.csv_file.read_text(encoding="utf-8")
    else:
        csv_text = SAMPLE_BENCHMARK_FIXTURE

    adapter = CsvBenchmarkAdapter()
    records = adapter.parse_csv(csv_text)

    with SessionLocal() as session:
        inserted, issues = persist_benchmark_series(
            session=session,
            benchmark_id=args.benchmark_id,
            records=records,
            source=args.source,
        )

        completed_at = datetime.now(UTC)
        run = PipelineRun(
            workflow="ingest_benchmark",
            code_version="1.0.0",
            configuration_hash="benchmark_v1",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts={"parsed": len(records), "inserted": inserted},
            quality_summary={"issues_count": len(issues), "issues": issues[:10]},
        )
        session.add(run)
        session.commit()

    print(
        f"Ingested {args.benchmark_id}: {len(records)} parsed, {inserted} inserted, "
        f"{len(issues)} issues reported"
    )


if __name__ == "__main__":
    main()
