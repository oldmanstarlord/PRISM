"""Calculate and persist the latest reproducible Layer 2 correlation MST."""

import argparse
from datetime import UTC, date, datetime, timedelta

from backend.app.correlation_mst.service import persist_mst
from backend.app.db.session import SessionLocal
from backend.app.sector_divergence.service import latest_market_snapshot


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("cutoff must include a timezone")
    return parsed.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-end", type=_date)
    parser.add_argument("--lookback-start", type=_date)
    parser.add_argument("--data-cutoff", type=_datetime)
    args = parser.parse_args()

    with SessionLocal() as session:
        latest_date, latest_cutoff = latest_market_snapshot(session)
        window_end = args.window_end or latest_date
        data_cutoff = args.data_cutoff or latest_cutoff
        lookback_start = args.lookback_start or (window_end - timedelta(days=220))
        result = persist_mst(
            session,
            window_end=window_end,
            lookback_start=lookback_start,
            data_cutoff=data_cutoff,
        )
    action = "created" if result.created else "reused"
    print(
        f"{action} MST run {result.run_id}: {result.node_count} nodes, "
        f"{result.edge_count} edges, {result.exclusion_count} exclusions"
    )


if __name__ == "__main__":
    main()
