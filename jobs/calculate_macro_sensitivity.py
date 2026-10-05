"""Job to compute and persist rolling sector macro sensitivities (FR-D3, FR-D4, FR-D6)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime

from sqlalchemy import desc, select

from backend.app.db.models import PriceDailyAdjusted
from backend.app.db.session import SessionLocal
from backend.app.macro.sensitivity import calculate_sector_macro_sensitivities

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_sensitivity_calculation(as_of: date | None = None, force: bool = False) -> None:
    session = SessionLocal()
    try:
        if as_of is None:
            latest_date = session.scalars(
                select(PriceDailyAdjusted.trade_date)
                .order_by(desc(PriceDailyAdjusted.trade_date))
                .limit(1)
            ).first()
            as_of = latest_date or datetime.now(UTC).date()

        logger.info(
            "Running sector macro sensitivity calculation for as_of=%s (force=%s)...",
            as_of,
            force,
        )
        results = calculate_sector_macro_sensitivities(session, as_of=as_of, force=force)
        sig_count = sum(1 for r in results if r.is_significant)
        logger.info(
            "Sensitivity calculation complete for as_of=%s: "
            "%d total sector-series pairs, %d statistically significant.",
            as_of,
            len(results),
            sig_count,
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate sector macro sensitivities")
    parser.add_argument("--as-of", type=str, help="As-of date (YYYY-MM-DD)", default=None)
    parser.add_argument("--force", action="store_true", help="Force recalculation")
    args = parser.parse_args()

    as_of_date = date.fromisoformat(args.as_of) if args.as_of else None
    run_sensitivity_calculation(as_of=as_of_date, force=args.force)


if __name__ == "__main__":
    main()
