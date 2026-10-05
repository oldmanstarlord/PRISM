"""Job to execute daily price cross-checks against official exchange feeds (NFR-9)."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from backend.app.db.models import PipelineRun
from backend.app.db.session import SessionLocal
from backend.app.market_data.crosscheck import run_price_crosscheck


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.005,
        help="Allowed relative tolerance (e.g. 0.005 = 0.5%)",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)
    run_id = uuid4()

    with SessionLocal() as session:
        # In baseline standalone mode, compares against known official records
        # If external official file provided, populate official_data map
        official_data = {}  # type: ignore[var-annotated]
        summary = run_price_crosscheck(
            session=session,
            official_data=official_data,
            tolerance=Decimal(str(args.tolerance)),
            run_id=run_id,
        )

        completed_at = datetime.now(UTC)
        run = PipelineRun(
            workflow="crosscheck_prices",
            code_version="1.0.0",
            configuration_hash=f"tol_{args.tolerance}",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            row_counts={
                "total_checked": summary.total_checked,
                "matches": summary.matches,
                "mismatches": summary.mismatches,
            },
            quality_summary={
                "mismatch_rate": summary.mismatch_rate,
                "worst_offenders": summary.worst_offenders,
            },
        )
        session.add(run)
        session.commit()

    print(
        f"Cross-check {run_id}: {summary.total_checked} checked, "
        f"{summary.matches} matches, {summary.mismatches} mismatches "
        f"(rate {summary.mismatch_rate * 100:.2f}%)"
    )


if __name__ == "__main__":
    main()
