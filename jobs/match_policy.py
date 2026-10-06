"""Policy matching job: matches news items against policy rules and generates
policy events (Step 11, D1, D3, D6).
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import NewsItem, PolicyEvent, PolicyRule
from backend.app.db.session import SessionLocal
from backend.app.policy.matcher import match_headline_to_rules
from backend.app.policy.provenance import VERIFIED_NEWS_SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("match_policy")


def run_match_policy(
    session: Session,
    include_draft: bool = True,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Match news_item records against policy_rule definitions and record
    policy_event rows (D1, D3, D6).
    """
    # 1. Query rules
    rule_query = select(PolicyRule)
    if not include_draft:
        rule_query = rule_query.where(PolicyRule.active.is_(True))

    rules = session.scalars(rule_query).all()
    logger.info("Loaded %d policy rules (include_draft=%s)", len(rules), include_draft)

    # 2. Query news items
    news_query = (
        select(NewsItem)
        .where(NewsItem.source.in_(VERIFIED_NEWS_SOURCES))
        .order_by(NewsItem.published_at.desc())
    )
    if limit:
        news_query = news_query.limit(limit)

    news_items = session.scalars(news_query).all()
    logger.info("Loaded %d news items to evaluate", len(news_items))

    # 3. Query existing event pairs for deduplication (news_item_id, rule_id, affected_industry)
    existing_events_rows = session.execute(
        select(PolicyEvent.news_item_id, PolicyEvent.rule_id, PolicyEvent.affected_industry)
    ).all()
    existing_events = {(row[0], row[1], row[2]) for row in existing_events_rows}

    stats = {
        "rules_evaluated": len(rules),
        "news_items_evaluated": len(news_items),
        "matches_found": 0,
        "events_inserted": 0,
        "skipped_existing": 0,
    }

    now_utc = datetime.now(UTC)

    for item in news_items:
        matches = match_headline_to_rules(item.headline, rules)
        for rule, ind, severity, evidence in matches:
            stats["matches_found"] += 1
            key = (item.id, rule.id, ind)
            if key in existing_events:
                stats["skipped_existing"] += 1
                continue

            event_row = PolicyEvent(
                id=uuid4(),
                news_item_id=item.id,
                rule_id=rule.id,
                matched_at=now_utc,
                affected_industry=ind,
                severity=severity,
                evidence=evidence,
            )

            if not dry_run:
                session.add(event_row)
                existing_events.add(key)

            stats["events_inserted"] += 1

    if not dry_run:
        session.commit()

    logger.info(
        "Policy matching completed. Matches: %d, Events inserted: %d, Skipped existing: %d",
        stats["matches_found"],
        stats["events_inserted"],
        stats["skipped_existing"],
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Match news against policy rules")
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only match active rules (exclude draft rules)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run without DB commits")
    parser.add_argument("--limit", type=int, default=None, help="Max news items to evaluate")

    args = parser.parse_args()

    with SessionLocal() as session:
        stats = run_match_policy(
            session=session,
            include_draft=not args.active_only,
            dry_run=args.dry_run,
            limit=args.limit,
        )
        print("Matching results:", stats)


if __name__ == "__main__":
    main()
