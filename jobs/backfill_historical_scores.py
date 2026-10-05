"""Backfill monthly point-in-time PRISM stock scores for honest validation."""

import argparse
from datetime import date

from backend.app.db.session import SessionLocal
from backend.app.validation.service import SURVIVORSHIP_WARNING, backfill_monthly_scores


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--score-config-version", default="1.0.0")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end must be on or after --start")

    print(f"SURVIVORSHIP WARNING: {SURVIVORSHIP_WARNING}")
    with SessionLocal() as session:
        run_ids = backfill_monthly_scores(
            session,
            args.start,
            args.end,
            score_config_version=args.score_config_version,
        )
    print(f"Created or reused {len(run_ids)} monthly score runs.")


if __name__ == "__main__":
    main()
