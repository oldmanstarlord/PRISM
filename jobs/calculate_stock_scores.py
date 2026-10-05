"""Calculate and persist reproducible multi-dimensional stock risk scores (Step 5)."""

import argparse
from datetime import UTC, date, datetime

from backend.app.db.session import SessionLocal
from backend.app.risk_score.service import run_stock_score_calculation
from backend.app.sector_divergence.service import latest_market_snapshot


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("data-cutoff must include a timezone")
    return parsed.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=_date, help="As-of trade date (YYYY-MM-DD)")
    parser.add_argument(
        "--config-version",
        type=str,
        default="1.0.0",
        help="Model config version for risk engine parameters",
    )
    parser.add_argument(
        "--data-cutoff",
        type=_datetime,
        help="Point-in-time publication/ingestion cutoff timestamp",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recomputation even if reproducible run exists",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        latest_date, latest_cutoff = latest_market_snapshot(session)
        as_of = args.as_of or latest_date
        data_cutoff = args.data_cutoff or latest_cutoff

        summary = run_stock_score_calculation(
            session=session,
            as_of=as_of,
            data_cutoff=data_cutoff,
            config_version=args.config_version,
            force=args.force,
        )

    action = "Created new" if summary.is_new else "Reused existing"
    print(
        f"{action} ScoreRun {summary.run_id}: as_of={summary.as_of_date}, "
        f"scored={summary.scored_securities}/{summary.total_securities} securities, "
        f"config_v={summary.config_version}"
    )


if __name__ == "__main__":
    main()
