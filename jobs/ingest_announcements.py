"""Idempotent ingestion job for exchange corporate announcements (Step 10, D4, D6)."""

from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data_sources.service import mark_source_success
from backend.app.db.models import EventItem, SourceDocument
from backend.app.db.session import SessionLocal
from backend.app.events.adapters.base import AnnouncementAdapter
from backend.app.events.adapters.csv_adapter import NseAnnouncementCsvAdapter
from backend.app.events.importance import calculate_event_importance
from backend.app.events.rules import (
    classify_announcement,
    link_security,
    resolve_effective_trading_date,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ingest_announcements")


def run_ingest_announcements(
    session: Session,
    source_file: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Ingest announcements into source_document and event_item tables idempotently (D4, D6)."""
    if not source_file:
        raise ValueError("--source-file is required; no live announcement source is configured")
    adapter: AnnouncementAdapter = NseAnnouncementCsvAdapter(file_path=source_file)

    raw_announcements = adapter.fetch_announcements(limit=limit)
    logger.info("Retrieved %d raw announcements from adapter", len(raw_announcements))

    stats = {
        "total_fetched": len(raw_announcements),
        "inserted_docs": 0,
        "inserted_events": 0,
        "skipped_existing": 0,
        "unmatched_securities": 0,
    }

    now_utc = datetime.now(UTC)

    for a in raw_announcements:
        # 1. Link to Security
        security, link_method = link_security(
            session=session,
            symbol=a.symbol,
            isin=a.isin,
            company_name=a.company_name,
        )

        if security is None:
            logger.warning(
                "Could not link announcement for %s (ISIN: %s) to universe security; skipping",
                a.symbol,
                a.isin,
            )
            stats["unmatched_securities"] += 1
            continue

        # 2. Check for duplicate ingestion by content_hash or source_doc_id
        content_bytes = f"{a.headline}\n{a.body or ''}".encode()
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        existing_doc = session.scalar(
            select(SourceDocument).where(
                (SourceDocument.source_doc_id == a.source_doc_id)
                | (SourceDocument.content_hash == content_hash)
            )
        )

        if existing_doc is not None:
            # Check if event_item also exists
            existing_event = session.scalar(
                select(EventItem).where(EventItem.source_document_id == existing_doc.id)
            )
            if existing_event is not None:
                stats["skipped_existing"] += 1
                continue
            source_doc = existing_doc
        else:
            source_doc = SourceDocument(
                id=uuid4(),
                security_id=security.id,
                source="NSE_MANUAL_IMPORT",
                source_doc_id=a.source_doc_id,
                doc_type="announcement",
                published_at=a.published_at,
                published_at_method="actual",
                ingested_at=now_utc,
                url=a.url,
                content_hash=content_hash,
                raw_path=None,
            )
            if not dry_run:
                session.add(source_doc)
                session.flush()
            stats["inserted_docs"] += 1

        # 3. Classify into canonical event type & risk direction
        event_type, risk_relevant, direction, rule_key = classify_announcement(
            session=session,
            source_category=a.source_category,
            headline=a.headline,
        )

        # 4. Calculate importance score resolving OQ-9
        importance, importance_components = calculate_event_importance(
            event_type=event_type,
            headline=a.headline,
            body=a.body,
        )
        importance_components["rule_key"] = rule_key
        importance_components["linking_method"] = link_method
        importance_components["risk_relevant"] = risk_relevant
        importance_components["direction"] = direction

        # 5. Determine effective trading date with after-close rollover
        eff_trading_date = resolve_effective_trading_date(
            session=session,
            published_at=a.published_at,
        )

        event_item = EventItem(
            id=uuid4(),
            source_document_id=source_doc.id,
            security_id=security.id,
            headline=a.headline,
            body=a.body,
            event_type=event_type,
            event_type_method="rule",
            published_at=a.published_at,
            effective_trading_date=eff_trading_date,
            importance=importance,
            importance_components=importance_components,
        )

        if not dry_run:
            session.add(event_item)
        stats["inserted_events"] += 1

        logger.info(
            "Ingested event for %s: [%s] '%s' (eff_date: %s, imp: %.1f)",
            a.symbol or security.isin,
            event_type,
            a.headline[:60],
            eff_trading_date,
            importance,
        )

    if not dry_run:
        mark_source_success(
            session,
            NseAnnouncementCsvAdapter.source_key,
            succeeded_at=now_utc,
            verified=True,
        )
        session.commit()
    else:
        session.rollback()
    logger.info("Ingestion finished: %s", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest exchange announcements idempotently.")
    parser.add_argument(
        "--source-file",
        type=str,
        required=True,
        help="Path to a manually downloaded official NSE announcement CSV export",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect without committing to DB")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        run_ingest_announcements(
            session=session,
            source_file=args.source_file,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
