"""Idempotent scoring job for event items using FinBERT / rule sentiment (Step 10, D1, D3)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import EventItem, ModelConfig, SourceDocument, TextScore
from backend.app.db.session import SessionLocal
from backend.app.events.finbert import score_announcement_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("score_events")


def run_score_events(
    session: Session,
    dry_run: bool = False,
    recompute: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Score unscored event items with FinBERT / rule sentiment engine (D1, D3, D6)."""
    # 1. Fetch approved model config
    cfg_row = session.scalar(
        select(ModelConfig)
        .where(
            ModelConfig.config_key == "event_risk_pressure",
            ModelConfig.status == "approved",
        )
        .order_by(ModelConfig.created_at.desc())
        .limit(1)
    )
    config = cfg_row.configuration if cfg_row else {}

    # 2. Query event items
    query = (
        select(EventItem)
        .join(SourceDocument, EventItem.source_document_id == SourceDocument.id)
        .where(
            SourceDocument.source == "NSE_MANUAL_IMPORT",
            SourceDocument.doc_type == "announcement",
        )
    )
    if not recompute:
        # Exclude items that already have a text_score
        scored_subq = select(TextScore.item_id).scalar_subquery()
        query = query.where(EventItem.id.not_in(scored_subq))

    query = query.order_by(EventItem.published_at.desc())
    if limit:
        query = query.limit(limit)

    event_items = session.scalars(query).all()
    logger.info("Found %d event items to score", len(event_items))

    stats = {
        "total_items": len(event_items),
        "scored": 0,
        "positive": 0,
        "negative": 0,
        "neutral": 0,
    }

    now_utc = datetime.now(UTC)

    for item in event_items:
        score_res = score_announcement_text(
            headline=item.headline,
            body=item.body,
            config=config,
        )

        text_score_row = TextScore(
            id=uuid4(),
            item_id=item.id,
            model_name=score_res.model_name,
            model_version=score_res.model_version,
            sentiment=score_res.sentiment,
            p_pos=score_res.p_pos,
            p_neg=score_res.p_neg,
            p_neu=score_res.p_neu,
            event_type=item.event_type,
            importance=item.importance,
            evidence_span=score_res.evidence_span,
            scored_at=now_utc,
        )

        if not dry_run:
            session.add(text_score_row)
            session.commit()

        stats["scored"] += 1
        stats[score_res.sentiment] += 1

        logger.info(
            "Scored event %s: sentiment=%s (pos=%.2f, neg=%.2f, neu=%.2f) - '%s'",
            item.id,
            score_res.sentiment,
            score_res.p_pos,
            score_res.p_neg,
            score_res.p_neu,
            (score_res.evidence_span or item.headline)[:60],
        )

    logger.info("Scoring completed: %s", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Score event items with sentiment and evidence.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without committing to DB")
    parser.add_argument(
        "--recompute", action="store_true", help="Re-score items with existing scores"
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to score")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        run_score_events(
            session=session,
            dry_run=args.dry_run,
            recompute=args.recompute,
            limit=args.limit,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
