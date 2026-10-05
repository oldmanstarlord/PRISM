"""Job to derive traded value, 20-day ADV, point-in-time market cap, and liquidity flags (FR-R3)."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from backend.app.db.models import PipelineRun
from backend.app.db.session import SessionLocal
from backend.app.market_data.market_stats import derive_all_market_stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    started_at = datetime.now(UTC)

    with SessionLocal() as session:
        completed_securities, total_records = derive_all_market_stats(session=session)

        completed_at = datetime.now(UTC)
        run = PipelineRun(
            workflow="derive_market_stats",
            code_version="1.0.0",
            configuration_hash="market_stats_v1",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts={
                "completed_securities": completed_securities,
                "total_records_derived": total_records,
            },
            quality_summary={},
        )
        session.add(run)
        session.commit()

    print(
        f"Derived market stats: {completed_securities} securities, "
        f"{total_records} daily stat records"
    )


if __name__ == "__main__":
    main()
