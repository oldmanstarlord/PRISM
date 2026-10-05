"""Idempotent ingestion job for news and policy press releases (Step 11, D4, D6)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ModelConfig, NewsItem, NewsSecurityLink, Security
from backend.app.db.session import SessionLocal
from backend.app.policy.adapters.base import NewsAdapter, RawNewsItem
from backend.app.policy.adapters.json_adapter import JsonNewsAdapter
from backend.app.policy.adapters.rss_adapter import RssNewsAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ingest_news")


def link_news_to_securities(
    session: Session,
    news_item: NewsItem,
    securities: list[tuple[Security, str]],
) -> list[NewsSecurityLink]:
    """Scan headline for universe stock symbols or prominent company names."""
    links: list[NewsSecurityLink] = []
    headline_upper = news_item.headline.upper()

    for sec, sym in securities:
        # Match symbol surrounded by word boundaries
        sym_match = False
        if f" {sym} " in f" {headline_upper} " or f"({sym})" in headline_upper:
            sym_match = True

        # Match company name (first word / major brand if distinct)
        name_match = False
        clean_name = sec.company_name.upper().replace("LIMITED", "").replace("LTD", "").strip()
        if len(clean_name) >= 4 and clean_name in headline_upper:
            name_match = True

        if sym_match:
            links.append(
                NewsSecurityLink(
                    news_item_id=news_item.id,
                    security_id=sec.id,
                    method="symbol",
                    confidence=0.95,
                )
            )
        elif name_match:
            links.append(
                NewsSecurityLink(
                    news_item_id=news_item.id,
                    security_id=sec.id,
                    method="name",
                    confidence=0.85,
                )
            )

    return links


def run_ingest_news(
    session: Session,
    source_type: str = "fixture",
    fixture_path: str | None = None,
    rss_url: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Ingest news items into news_item table idempotently deduplicated by content_hash (D4, D6)."""
    # 1. Fetch config if available
    cfg_row = session.scalar(
        select(ModelConfig)
        .where(
            ModelConfig.config_key == "news_policy_pressure",
            ModelConfig.status.in_(["approved", "draft"]),
        )
        .order_by(ModelConfig.created_at.desc())
        .limit(1)
    )
    config = cfg_row.configuration if cfg_row else {}
    poll_interval = config.get("poll_interval_minutes", 30)
    logger.info("Configured news poll interval: %d minutes", poll_interval)

    # 2. Select Adapter
    adapter: NewsAdapter
    if source_type == "rss":
        adapter = RssNewsAdapter(rss_url=rss_url)
    else:
        adapter = JsonNewsAdapter(file_path=fixture_path)

    raw_items: list[RawNewsItem] = adapter.fetch_news(limit=limit)
    logger.info("Fetched %d raw news items from adapter (%s)", len(raw_items), source_type)

    # 3. Query existing content hashes for deduplication
    existing_hashes = set(session.scalars(select(NewsItem.content_hash)).all())

    # Pre-fetch active securities and symbols for ticker linking
    from backend.app.db.models import SecurityAlias

    alias_stmt = (
        select(Security, SecurityAlias.symbol)
        .join(SecurityAlias, SecurityAlias.security_id == Security.id)
        .where(Security.is_active.is_(True))
    )
    securities = [(row[0], row[1]) for row in session.execute(alias_stmt).all()]

    stats = {
        "total_fetched": len(raw_items),
        "inserted_news": 0,
        "skipped_duplicate": 0,
        "security_links_created": 0,
    }

    now_utc = datetime.now(UTC)

    for item in raw_items:
        if item.content_hash in existing_hashes:
            stats["skipped_duplicate"] += 1
            continue

        news_row = NewsItem(
            id=uuid4(),
            source=item.source,
            published_at=item.published_at,
            ingested_at=now_utc,
            headline=item.headline,
            url=item.url,
            content_hash=item.content_hash,
        )

        if not dry_run:
            session.add(news_row)
            existing_hashes.add(item.content_hash)

            # Security links
            links = link_news_to_securities(session, news_row, securities)
            for link in links:
                session.add(link)
            stats["security_links_created"] += len(links)

        stats["inserted_news"] += 1

    if not dry_run:
        session.commit()

    logger.info(
        "News ingestion complete. Inserted: %d, Skipped (duplicate): %d, Sec links: %d",
        stats["inserted_news"],
        stats["skipped_duplicate"],
        stats["security_links_created"],
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest news items from official RSS or fixtures")
    parser.add_argument(
        "--source",
        choices=["fixture", "rss"],
        default="fixture",
        help="Source adapter type (default: fixture)",
    )
    parser.add_argument("--fixture-path", default=None, help="Path to local news JSON fixture")
    parser.add_argument("--rss-url", default=None, help="RSS feed URL for regulatory releases")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without DB commits")
    parser.add_argument("--limit", type=int, default=None, help="Max items to fetch")

    args = parser.parse_args()

    with SessionLocal() as session:
        stats = run_ingest_news(
            session=session,
            source_type=args.source,
            fixture_path=args.fixture_path,
            rss_url=args.rss_url,
            dry_run=args.dry_run,
            limit=args.limit,
        )
        print("Ingestion results:", stats)


if __name__ == "__main__":
    main()
