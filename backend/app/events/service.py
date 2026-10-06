"""Service layer for querying explainable events and announcements."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import EventItem, Security, SecurityAlias, SourceDocument, TextScore
from backend.app.events.schemas import EventItemOut, RecentEventsResponse, StockEventsResponse


def _build_event_out(
    item: EventItem,
    doc: SourceDocument | None,
    text_score: TextScore | None,
    symbol: str | None,
    company_name: str | None,
) -> EventItemOut:
    headline = item.headline
    source_url = doc.url if doc else None

    return EventItemOut(
        id=item.id,
        source_document_id=item.source_document_id,
        security_id=item.security_id,
        symbol=symbol,
        company_name=company_name,
        event_type=item.event_type,
        event_type_method=item.event_type_method,
        published_at=item.published_at,
        effective_trading_date=item.effective_trading_date,
        importance=item.importance,
        importance_components=item.importance_components or {},
        headline=headline,
        source_url=source_url,
        sentiment=text_score.sentiment if text_score else None,
        p_pos=text_score.p_pos if text_score else None,
        p_neg=text_score.p_neg if text_score else None,
        p_neu=text_score.p_neu if text_score else None,
        evidence_span=text_score.evidence_span if text_score else None,
        scored_at=text_score.scored_at if text_score else None,
        model_name=text_score.model_name if text_score else None,
        model_version=text_score.model_version if text_score else None,
    )


def get_stock_events(
    session: Session,
    symbol: str,
    limit: int = 50,
) -> StockEventsResponse | None:
    """Retrieve chronologically ordered events for a stock by symbol."""
    clean_sym = symbol.strip().upper()

    alias = session.scalar(select(SecurityAlias).where(SecurityAlias.symbol == clean_sym))
    if not alias:
        return None

    sec = session.get(Security, alias.security_id)
    if not sec:
        return None

    # Query events for security
    stmt = (
        select(EventItem, SourceDocument, TextScore)
        .outerjoin(SourceDocument, EventItem.source_document_id == SourceDocument.id)
        .outerjoin(TextScore, EventItem.id == TextScore.item_id)
        .where(
            EventItem.security_id == sec.id,
            SourceDocument.source == "NSE_MANUAL_IMPORT",
            SourceDocument.doc_type == "announcement",
        )
        .order_by(desc(EventItem.effective_trading_date), desc(EventItem.published_at))
        .limit(limit)
    )

    rows = session.execute(stmt).all()
    events = [
        _build_event_out(item, doc, ts, clean_sym, sec.company_name) for item, doc, ts in rows
    ]

    return StockEventsResponse(
        symbol=clean_sym,
        company_name=sec.company_name,
        total_events=len(events),
        events=events,
    )


def get_recent_events(
    session: Session,
    event_type: str | None = None,
    min_importance: float | None = None,
    since_date: date | None = None,
    limit: int = 50,
) -> RecentEventsResponse:
    """Retrieve recent corporate announcements across all stocks with optional filters."""
    stmt = (
        select(EventItem, SourceDocument, TextScore, Security, SecurityAlias)
        .outerjoin(SourceDocument, EventItem.source_document_id == SourceDocument.id)
        .outerjoin(TextScore, EventItem.id == TextScore.item_id)
        .join(Security, EventItem.security_id == Security.id)
        .outerjoin(SecurityAlias, Security.id == SecurityAlias.security_id)
        .where(
            SourceDocument.source == "NSE_MANUAL_IMPORT",
            SourceDocument.doc_type == "announcement",
        )
    )

    if event_type:
        stmt = stmt.where(EventItem.event_type == event_type.strip().lower())
    if min_importance is not None:
        stmt = stmt.where(EventItem.importance >= min_importance)
    if since_date is not None:
        stmt = stmt.where(EventItem.effective_trading_date >= since_date)

    stmt = stmt.order_by(
        desc(EventItem.effective_trading_date), desc(EventItem.published_at)
    ).limit(limit)

    rows = session.execute(stmt).all()

    # Deduplicate security alias if multiple aliases exist
    seen_items: set[UUID] = set()
    events: list[EventItemOut] = []

    for item, doc, ts, sec, alias in rows:
        if item.id in seen_items:
            continue
        seen_items.add(item.id)
        events.append(
            _build_event_out(
                item,
                doc,
                ts,
                alias.symbol if alias else None,
                sec.company_name if sec else None,
            )
        )

    return RecentEventsResponse(
        total=len(events),
        events=events,
    )
