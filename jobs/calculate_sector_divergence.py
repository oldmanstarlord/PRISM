"""Calculate and persist the latest reproducible Layer 1 result set."""

import argparse
from datetime import UTC, date, datetime, timedelta

from backend.app.db.session import SessionLocal
from backend.app.sector_divergence.service import latest_market_snapshot, persist_calculation


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("cutoff must include a timezone")
    return parsed.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal-date", type=_date)
    parser.add_argument("--lookback-start", type=_date)
    parser.add_argument("--data-cutoff", type=_datetime)
    args = parser.parse_args()

    with SessionLocal() as session:
        latest_date, latest_cutoff = latest_market_snapshot(session)
        signal_date = args.signal_date or latest_date
        data_cutoff = args.data_cutoff or latest_cutoff
        lookback_start = args.lookback_start or (signal_date - timedelta(days=180))
        result = persist_calculation(
            session,
            signal_date=signal_date,
            lookback_start=lookback_start,
            data_cutoff=data_cutoff,
        )
    action = "created" if result.created else "reused"
    print(
        f"{action} run {result.run_id}: {result.score_count} scores, "
        f"{result.issue_count} issues, {result.exclusion_count} exclusions"
    )


if __name__ == "__main__":
    main()
