"""Poll filings/news and incrementally rescore only newly affected securities."""

import subprocess
import sys
from datetime import UTC, datetime

from sqlalchemy import desc, select

from backend.app.db.models import EventItem, NewsItem, NewsSecurityLink, ScoreRun
from backend.app.db.session import SessionLocal
from backend.app.operations.service import incremental_rescore


def _run(module: str) -> None:
    subprocess.run([sys.executable, "-m", module], check=True)  # noqa: S603


def main() -> None:
    started = datetime.now(UTC)
    for module in (
        "jobs.ingest_announcements",
        "jobs.score_events",
        "jobs.ingest_news",
        "jobs.match_policy",
    ):
        _run(module)
    with SessionLocal() as session:
        affected = set(
            session.scalars(
                select(EventItem.security_id).where(EventItem.created_at >= started)
            ).all()
        )
        affected.update(
            session.scalars(
                select(NewsSecurityLink.security_id)
                .join(NewsItem, NewsItem.id == NewsSecurityLink.news_item_id)
                .where(NewsItem.ingested_at >= started)
            ).all()
        )
        parent = session.scalars(
            select(ScoreRun)
            .where(ScoreRun.status == "completed", ScoreRun.run_kind == "full")
            .order_by(desc(ScoreRun.completed_at))
        ).first()
        if parent is None:
            print("No completed parent score run; incremental rescore skipped.")
            return
        for security_id in sorted(affected, key=str):
            incremental_rescore(session, security_id, parent.id, data_cutoff=datetime.now(UTC))
    print(f"Incrementally rescored {len(affected)} affected stocks; prices remain end-of-day.")


if __name__ == "__main__":
    main()
