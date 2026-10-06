"""Calculate incremental, idempotent news impacts from allowlisted live feeds."""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from backend.app.db.session import SessionLocal
from backend.app.news_impact.service import run_incremental_news_impact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--news-id", action="append", default=[])
    args = parser.parse_args()
    ids = [UUID(value) for value in args.news_id] or None
    with SessionLocal() as session:
        result = run_incremental_news_impact(session, ids)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
