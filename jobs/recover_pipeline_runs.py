"""Mark abandoned running pipeline records failed without replacing published results."""

import argparse
from datetime import timedelta

from backend.app.db.session import SessionLocal
from backend.app.pipeline.service import recover_stale_pipeline_runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--older-than-minutes", type=int, default=120)
    args = parser.parse_args()
    if args.older_than_minutes < 1:
        parser.error("--older-than-minutes must be positive")
    with SessionLocal() as session:
        count = recover_stale_pipeline_runs(
            session, stale_after=timedelta(minutes=args.older_than_minutes)
        )
    print(f"Recovered {count} abandoned pipeline run(s)")


if __name__ == "__main__":
    main()
