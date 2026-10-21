"""Collect news once, or poll at the configured interval with --watch."""

import argparse
import time

from backend.app.core.config import settings
from backend.app.news.collection import NewsService
from backend.app.news.store import RefreshBlocked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    service = NewsService(settings)
    while True:
        try:
            service.collect(service.prepare())
        except RefreshBlocked as exc:
            print(exc)
        state = service.status()
        print(state)
        if not args.watch:
            if state["error"]:
                raise SystemExit(1)
            return
        time.sleep(settings.news_refresh_minutes * 60)


if __name__ == "__main__":
    main()
