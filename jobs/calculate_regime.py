"""Job to calculate and persist market regime (FR-F4)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime

from sqlalchemy import desc, select

from backend.app.db.models import PriceDailyAdjusted
from backend.app.db.session import SessionLocal
from backend.app.macro.regime import classify_market_regime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_regime_calculation(as_of: date | None = None, force: bool = False) -> None:
    session = SessionLocal()
    try:
        if as_of is None:
            # Default to latest price date in DB or today
            latest_date = session.scalars(
                select(PriceDailyAdjusted.trade_date)
                .order_by(desc(PriceDailyAdjusted.trade_date))
                .limit(1)
            ).first()
            as_of = latest_date or datetime.now(UTC).date()

        logger.info("Running market regime calculation for as_of=%s (force=%s)...", as_of, force)
        result = classify_market_regime(session, as_of=as_of, force=force)
        logger.info(
            "Regime calculation completed: as_of=%s regime=%s (is_new=%s) features=%s",
            result.as_of,
            result.regime,
            result.is_new,
            result.features,
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate PRISM market regime")
    parser.add_argument("--as-of", type=str, help="As-of date (YYYY-MM-DD)", default=None)
    parser.add_argument("--force", action="store_true", help="Force recalculation")
    args = parser.parse_args()

    as_of_date = date.fromisoformat(args.as_of) if args.as_of else None
    run_regime_calculation(as_of=as_of_date, force=args.force)


if __name__ == "__main__":
    main()
