"""Read-only contamination audit for the pre-Step-12 cleanup checkpoint."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from backend.app.db.models import (
    EventItem,
    MacroObservation,
    MarketRegime,
    NewsItem,
    NewsSecurityLink,
    PolicyEvent,
    ScoreComponentValue,
    ScoreRun,
    SectorMacroSensitivity,
    SourceDocument,
    StockRiskResult,
    TextScore,
)
from backend.app.db.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _summary(rows: list[Any], date_attr: str, *, examples: int = 3) -> dict[str, Any]:
    dates = [getattr(row, date_attr) for row in rows if getattr(row, date_attr) is not None]
    return {
        "count": len(rows),
        "first": min(dates).isoformat() if dates else None,
        "last": max(dates).isoformat() if dates else None,
        "example_ids": [str(row.id) for row in rows[:examples]],
    }


def main() -> None:
    announcement_fixture = json.loads((FIXTURES / "announcements.json").read_text("utf-8"))
    announcement_doc_ids = {row["source_doc_id"] for row in announcement_fixture}
    announcement_headlines = {row["headline"].strip() for row in announcement_fixture}
    announcement_hashes = {
        hashlib.sha256(f"{row['headline']}\n{row.get('body') or ''}".encode()).hexdigest()
        for row in announcement_fixture
    }

    news_fixture = json.loads((FIXTURES / "news.json").read_text("utf-8"))
    news_headlines = {row["headline"].strip() for row in news_fixture}
    news_urls = {row["url"].strip() for row in news_fixture}

    fixture_macro: set[tuple[str, object, float]] = set()
    for path in sorted((FIXTURES / "macro").glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw_date = row.get("date") or row.get("obs_date")
                raw_value = row.get("value") or row.get("close")
                if raw_date and raw_value is not None:
                    fixture_macro.add((path.stem, raw_date.strip(), float(raw_value)))

    with SessionLocal() as session:
        source_docs = list(
            session.scalars(
                select(SourceDocument)
                .where(
                    (SourceDocument.source_doc_id.in_(announcement_doc_ids))
                    | (SourceDocument.content_hash.in_(announcement_hashes))
                )
                .order_by(SourceDocument.published_at, SourceDocument.id)
            ).all()
        )
        source_doc_ids = {row.id for row in source_docs}
        event_items = list(
            session.scalars(
                select(EventItem)
                .where(
                    (EventItem.source_document_id.in_(source_doc_ids))
                    | (EventItem.headline.in_(announcement_headlines))
                )
                .order_by(EventItem.published_at, EventItem.id)
            ).all()
        )
        event_ids = {row.id for row in event_items}
        text_scores = list(
            session.scalars(
                select(TextScore)
                .where(TextScore.item_id.in_(event_ids))
                .order_by(TextScore.scored_at, TextScore.id)
            ).all()
        )

        news_items = list(
            session.scalars(
                select(NewsItem)
                .where((NewsItem.headline.in_(news_headlines)) | (NewsItem.url.in_(news_urls)))
                .order_by(NewsItem.published_at, NewsItem.id)
            ).all()
        )
        news_ids = {row.id for row in news_items}
        news_links = list(
            session.scalars(
                select(NewsSecurityLink)
                .where(NewsSecurityLink.news_item_id.in_(news_ids))
                .order_by(NewsSecurityLink.created_at, NewsSecurityLink.id)
            ).all()
        )
        policy_events = list(
            session.scalars(
                select(PolicyEvent)
                .where(PolicyEvent.news_item_id.in_(news_ids))
                .order_by(PolicyEvent.matched_at, PolicyEvent.id)
            ).all()
        )

        all_macro = list(session.scalars(select(MacroObservation)).all())
        macro_matches = [
            row
            for row in all_macro
            if (row.series_key, row.obs_date.isoformat(), float(row.value)) in fixture_macro
        ]
        matched_by_series: dict[str, list[MacroObservation]] = defaultdict(list)
        total_by_series: dict[str, list[MacroObservation]] = defaultdict(list)
        for macro_row in macro_matches:
            matched_by_series[macro_row.series_key].append(macro_row)
        for macro_row in all_macro:
            total_by_series[macro_row.series_key].append(macro_row)

        macro_cutoff = min((row.ingested_at for row in macro_matches), default=None)
        event_cutoff = min((row.ingested_at for row in source_docs), default=None)
        news_cutoff = min((row.ingested_at for row in news_items), default=None)
        contamination_cutoffs = [
            value for value in (macro_cutoff, event_cutoff, news_cutoff) if value
        ]
        earliest_cutoff = min(contamination_cutoffs) if contamination_cutoffs else None

        regimes = list(
            session.scalars(select(MarketRegime).order_by(MarketRegime.created_at)).all()
        )
        sensitivities = list(
            session.scalars(
                select(SectorMacroSensitivity).order_by(SectorMacroSensitivity.created_at)
            ).all()
        )
        if macro_cutoff:
            regimes = [row for row in regimes if row.created_at >= macro_cutoff]
            sensitivities = [row for row in sensitivities if row.created_at >= macro_cutoff]

        affected_components = {"event_risk_pressure", "macro_exposure", "news_policy_pressure"}
        component_values = list(
            session.scalars(
                select(ScoreComponentValue)
                .where(ScoreComponentValue.component_id.in_(affected_components))
                .order_by(ScoreComponentValue.id)
            ).all()
        )
        score_runs = list(session.scalars(select(ScoreRun).order_by(ScoreRun.started_at)).all())
        if earliest_cutoff:
            score_runs = [row for row in score_runs if row.started_at >= earliest_cutoff]
        run_ids = {row.id for row in score_runs}
        risk_results = list(
            session.scalars(
                select(StockRiskResult)
                .where(StockRiskResult.run_id.in_(run_ids))
                .order_by(StockRiskResult.computed_at)
            ).all()
        )

        report = {
            "fixture_announcements": {
                "source_document": _summary(source_docs, "published_at"),
                "event_item": _summary(event_items, "published_at"),
                "text_score": _summary(text_scores, "scored_at"),
            },
            "fixture_news": {
                "news_item": _summary(news_items, "published_at"),
                "news_security_link": _summary(news_links, "created_at"),
                "policy_event": _summary(policy_events, "matched_at"),
            },
            "fixture_macro_matches": {
                key: _summary(sorted(rows, key=lambda row: row.obs_date), "obs_date")
                for key, rows in sorted(matched_by_series.items())
            },
            "macro_database_totals": {
                key: {
                    "count": len(rows),
                    "last_obs_date": max(row.obs_date for row in rows).isoformat(),
                    "source_counts": {
                        str(source): count
                        for source, count in session.execute(
                            select(MacroObservation.source, func.count())
                            .where(MacroObservation.series_key == key)
                            .group_by(MacroObservation.source)
                        ).all()
                    },
                }
                for key, rows in sorted(total_by_series.items())
            },
            "derived_after_contamination": {
                "market_regime": _summary(regimes, "as_of"),
                "sector_macro_sensitivity": _summary(sensitivities, "window_end"),
                "score_component_value": {
                    **_summary(component_values, "data_as_of"),
                    "by_component": dict(
                        sorted(
                            (key, sum(row.component_id == key for row in component_values))
                            for key in affected_components
                        )
                    ),
                },
                "score_run": _summary(score_runs, "started_at"),
                "stock_risk_result": _summary(risk_results, "computed_at"),
            },
            "contamination_cutoffs": {
                "announcements": event_cutoff.isoformat() if event_cutoff else None,
                "news": news_cutoff.isoformat() if news_cutoff else None,
                "macro": macro_cutoff.isoformat() if macro_cutoff else None,
            },
        }
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
