"""Incremental news ingestion, NLP scoring, and freshness reporting pipeline job."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from backend.app.db.session import SessionLocal
from backend.app.news.service import NewsIntelligenceService


def run_news_ingestion(
    symbols: list[str] | None = None,
    max_per_symbol: int = 5,
    persist_db: bool = True,
) -> dict[str, int | str]:
    """Execute news feed ingestion, matching, deduplication, and persistence."""
    default_symbols = [
        "RELIANCE",
        "TCS",
        "HDFCBANK",
        "INFY",
        "ICICIBANK",
        "BHARTIARTL",
        "SBIN",
        "ITC",
    ]
    target_symbols = symbols or default_symbols

    now_iso = datetime.now(UTC).isoformat()
    print(f"[{now_iso}] Starting news ingestion for {len(target_symbols)} symbols...")

    # Fast, hermetic execution for pipeline
    service = NewsIntelligenceService(use_transformer=False)

    holdings_mock = [{"symbol": sym, "weight": 1.0 / len(target_symbols)} for sym in target_symbols]

    db_session = SessionLocal() if persist_db else None

    try:
        summary = service.get_portfolio_news_intelligence(
            holdings=holdings_mock,
            db=db_session,
            max_articles_per_holding=max_per_symbol,
        )

        print(f"Provider: {summary.provider_name} (Status: {summary.provider_status})")
        print(f"Tracked Articles: {summary.total_articles_tracked}")
        print(f"Deduplicated Articles: {summary.deduplicated_article_count}")
        print(f"Ambiguous Matches Needing Review: {summary.ambiguous_match_count}")
        sent_info = (
            f"Portfolio News Sentiment Score: {summary.portfolio_sentiment_score:+.4f} "
            f"({summary.portfolio_sentiment_label})"
        )
        print(sent_info)

        return {
            "status": "completed",
            "provider_status": summary.provider_status,
            "total_articles": summary.total_articles_tracked,
            "deduplicated_articles": summary.deduplicated_article_count,
            "ambiguous_matches": summary.ambiguous_match_count,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    finally:
        if db_session is not None:
            db_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="PRISM Phase 5 News Ingestion Job")
    parser.add_argument("--symbols", nargs="+", help="Symbols to fetch news for")
    parser.add_argument("--max", type=int, default=5, help="Max articles per symbol")
    parser.add_argument(
        "--no-db", action="store_true", help="Run in dry-run mode without DB writes"
    )
    parser.add_argument(
        "--evaluate", type=str, help="Evaluate accuracy on user ground-truth CSV template"
    )

    args = parser.parse_args()

    if args.evaluate:
        service = NewsIntelligenceService(use_transformer=False)
        print(f"Evaluating model against user ground truth: {args.evaluate}...")
        try:
            res = service.evaluate_against_user_labels(args.evaluate)
            print(f"Evaluated Samples: {res.evaluated_samples}")
            print(f"Sentiment Accuracy: {res.sentiment_accuracy * 100:.2f}%")
            print(f"Entity Matching Precision: {res.entity_matching_precision * 100:.2f}%")
            print(f"Notice: {res.governance_notice}")
        except Exception as e:
            print(f"Evaluation error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    run_news_ingestion(symbols=args.symbols, max_per_symbol=args.max, persist_db=not args.no_db)


if __name__ == "__main__":
    main()
