"""Tests for EventRiskPressureComponent: recency decay, positive cap, no-lookahead (D1, D3, D4)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.app.db.models import EventItem, Security, SourceDocument, TextScore
from backend.app.risk_score.components.base import RiskContext
from backend.app.risk_score.components.events import EventRiskPressureComponent

IST = ZoneInfo("Asia/Kolkata")


def test_recency_decay_and_offset_cap_math(session) -> None:
    """Hand-calculated test:

    - Event 1 (today, delta_t=0): negative, importance=10.0 -> decayed=10.0 * 2^0 = 10.0
    - Event 2 (14 days ago, delta_t=14): negative, importance=8.0 -> decayed=8.0 * 2^(-14/14) = 4.0
    Total gross negative = 10.0 + 4.0 = 14.0

    - Event 3 (today, delta_t=0): positive, importance=10.0 -> decayed=10.0
    Max allowable positive offset = 0.30 * 14.0 = 4.2
    Effective positive offset = min(10.0, 4.2) = 4.2

    Net pressure = 14.0 - 4.2 = 9.8
    """
    sec = Security(
        id=uuid4(),
        isin=f"INE{uuid4().hex[:9].upper()}",
        company_name="Test Recency Corp",
        sector="Technology",
        industry="IT Services",
    )
    session.add(sec)
    session.flush()

    as_of = date(2024, 3, 20)
    cutoff = datetime(2024, 3, 20, 23, 59, 59, tzinfo=IST)

    doc = SourceDocument(
        id=uuid4(),
        security_id=sec.id,
        source="NSE_MANUAL_IMPORT",
        doc_type="announcement",
        published_at=datetime(2024, 3, 20, 10, 0, tzinfo=IST),
        ingested_at=datetime(2024, 3, 20, 10, 5, tzinfo=IST),
        content_hash=f"test_hash_decay_{uuid4()}",
    )
    session.add(doc)
    session.flush()

    # Event 1: Today, negative, importance=10.0
    e1 = EventItem(
        id=uuid4(),
        source_document_id=doc.id,
        security_id=sec.id,
        headline="Penalty imposed",
        event_type="regulatory_action",
        published_at=datetime(2024, 3, 20, 10, 0, tzinfo=IST),
        effective_trading_date=as_of,
        importance=10.0,
        importance_components={"risk_relevant": True, "direction": "negative"},
    )
    session.add(e1)
    session.flush()

    ts1 = TextScore(
        item_id=e1.id,
        model_name="prism_rule_sentiment",
        model_version="1.0.0",
        sentiment="negative",
        p_pos=0.05,
        p_neg=0.90,
        p_neu=0.05,
        evidence_span="Penalty imposed",
    )

    # Event 2: 14 days ago (half-life), negative, importance=8.0
    e2 = EventItem(
        id=uuid4(),
        source_document_id=doc.id,
        security_id=sec.id,
        headline="Downgrade watch",
        event_type="debt_rating",
        published_at=datetime(2024, 3, 6, 10, 0, tzinfo=IST),
        effective_trading_date=date(2024, 3, 6),
        importance=8.0,
        importance_components={"risk_relevant": True, "direction": "negative"},
    )
    session.add(e2)
    session.flush()

    ts2 = TextScore(
        item_id=e2.id,
        model_name="prism_rule_sentiment",
        model_version="1.0.0",
        sentiment="negative",
        p_pos=0.05,
        p_neg=0.90,
        p_neu=0.05,
        evidence_span="Downgrade watch",
    )

    # Event 3: Today, positive, importance=10.0
    e3 = EventItem(
        id=uuid4(),
        source_document_id=doc.id,
        security_id=sec.id,
        headline="Major contract win",
        event_type="ma_order",
        published_at=datetime(2024, 3, 20, 10, 0, tzinfo=IST),
        effective_trading_date=as_of,
        importance=10.0,
        importance_components={"risk_relevant": False, "direction": "positive"},
    )
    session.add(e3)
    session.flush()

    ts3 = TextScore(
        item_id=e3.id,
        model_name="prism_rule_sentiment",
        model_version="1.0.0",
        sentiment="positive",
        p_pos=0.90,
        p_neg=0.05,
        p_neu=0.05,
        evidence_span="Major contract win",
    )

    session.add_all([ts1, ts2, ts3])
    session.commit()

    component = EventRiskPressureComponent()
    ctx = RiskContext(
        session=session,
        as_of=as_of,
        data_cutoff=cutoff,
        config={
            "event_risk_pressure": {
                "recency_half_life_days": 14,
                "positive_offset_cap": 0.30,
            }
        },
    )

    vals = component.compute(as_of, [(sec.id, "TEST", sec.industry or "IT")], ctx)
    assert len(vals) == 1
    res = vals[0]
    assert res.raw_value is not None
    assert round(res.raw_value, 2) == 9.80
    assert res.status == "ok"
    assert res.evidence_ref["gross_negative_pressure"] == 14.0
    assert res.evidence_ref["allowed_positive_offset"] == 4.2
    assert res.evidence_ref["net_pressure"] == 9.8

    # Cleanup
    session.query(TextScore).filter(TextScore.item_id.in_([e1.id, e2.id, e3.id])).delete()
    session.query(EventItem).filter_by(security_id=sec.id).delete()
    session.query(SourceDocument).filter_by(security_id=sec.id).delete()
    session.delete(sec)
    session.commit()


def test_no_look_ahead_event_filtering(session) -> None:
    """Events published after as_of/cutoff must be strictly excluded (D4)."""
    sec = Security(
        id=uuid4(),
        isin=f"INE{uuid4().hex[:9].upper()}",
        company_name="Test No Lookahead Corp",
        sector="Technology",
        industry="IT Services",
    )
    session.add(sec)
    session.flush()

    as_of = date(2024, 3, 10)
    cutoff = datetime(2024, 3, 10, 23, 59, 59, tzinfo=IST)

    doc = SourceDocument(
        id=uuid4(),
        security_id=sec.id,
        source="NSE_MANUAL_IMPORT",
        doc_type="announcement",
        published_at=datetime(2024, 3, 15, 10, 0, tzinfo=IST),
        ingested_at=datetime(2024, 3, 15, 10, 5, tzinfo=IST),
        content_hash=f"test_hash_future_{uuid4()}",
    )
    session.add(doc)
    session.flush()

    # Future event (effective date 2024-03-15 > as_of 2024-03-10)
    future_event = EventItem(
        id=uuid4(),
        source_document_id=doc.id,
        security_id=sec.id,
        headline="Future event",
        event_type="regulatory_action",
        published_at=datetime(2024, 3, 15, 10, 0, tzinfo=IST),
        effective_trading_date=date(2024, 3, 15),
        importance=10.0,
        importance_components={"risk_relevant": True, "direction": "negative"},
    )
    session.add(future_event)
    session.commit()

    component = EventRiskPressureComponent()
    ctx = RiskContext(
        session=session,
        as_of=as_of,
        data_cutoff=cutoff,
        config={},
    )

    vals = component.compute(as_of, [(sec.id, "TEST", sec.industry or "IT")], ctx)
    assert len(vals) == 1
    res = vals[0]
    # Neither the future event nor its future source document can establish coverage.
    assert res.raw_value is None
    assert res.status == "missing"
    assert res.evidence_ref["event_count"] == 0
    assert res.evidence_ref["reason"] == "no_point_in_time_announcement_source_coverage"

    # Cleanup
    session.query(EventItem).filter_by(security_id=sec.id).delete()
    session.query(SourceDocument).filter_by(security_id=sec.id).delete()
    session.delete(sec)
    session.commit()
