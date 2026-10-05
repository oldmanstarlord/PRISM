"""Tests for governance service.

Deduplication, restatement versioning, and point-in-time reads (D4, D6).
"""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import Security
from backend.app.governance.adapters.base import (
    ParsedInsiderTradeRecord,
    ParsedShareholdingRecord,
)
from backend.app.governance.service import (
    _insider_content_hash,
    _shareholding_content_hash,
    get_shareholding_as_of,
    ingest_insider_trade_records,
    ingest_shareholding_records,
)


def _setup_sqlite_db() -> Session:
    """Create in-memory SQLite session with schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def test_shareholding_content_hash_deterministic() -> None:
    """Same fields produce identical content_hash (D6)."""
    sec_id = uuid4()
    q_end = date(2025, 12, 31)
    pub_at = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)

    h1 = _shareholding_content_hash(sec_id, q_end, 50.0, 10.0, 20.0, 15.0, 15.0, pub_at)
    h2 = _shareholding_content_hash(sec_id, q_end, 50.0, 10.0, 20.0, 15.0, 15.0, pub_at)

    assert h1 == h2
    assert len(h1) == 64


def test_insider_content_hash_deterministic() -> None:
    """Same insider trade fields produce identical content_hash (D6)."""
    sec_id = uuid4()
    txn_date = date(2025, 11, 1)
    pub_at = datetime(2025, 11, 2, 8, 30, tzinfo=UTC)

    h1 = _insider_content_hash(sec_id, "Promoter", "sell", 10000, txn_date, pub_at)
    h2 = _insider_content_hash(sec_id, "Promoter", "sell", 10000, txn_date, pub_at)

    assert h1 == h2
    assert len(h1) == 64


def test_shareholding_ingestion_idempotence_and_deduplication() -> None:
    """Re-ingesting the exact same record skips duplicates (D6)."""
    session = _setup_sqlite_db()
    sec_id = uuid4()
    sec = Security(id=sec_id, company_name="Test Company", isin="INE000000001", is_active=True)
    session.add(sec)
    session.commit()

    records = [
        ParsedShareholdingRecord(
            quarter_end=date(2025, 12, 31),
            promoter_pct=60.0,
            promoter_pledged_pct_of_promoter=5.0,
            fii_pct=20.0,
            dii_pct=10.0,
            public_pct=10.0,
            published_at=datetime(2026, 1, 10, 12, 0, tzinfo=UTC),
        )
    ]

    ingest_time = datetime(2026, 1, 11, 0, 0, tzinfo=UTC)

    # First ingestion: 1 inserted, 0 skipped
    res1 = ingest_shareholding_records(session, sec_id, records, ingest_time)
    assert res1["inserted"] == 1
    assert res1["skipped_duplicate"] == 0

    # Repeat ingestion (idempotent run): 0 inserted, 1 skipped
    res2 = ingest_shareholding_records(session, sec_id, records, ingest_time)
    assert res2["inserted"] == 0
    assert res2["skipped_duplicate"] == 1


def test_shareholding_point_in_time_no_lookahead() -> None:
    """Filing published after cutoff date is NOT visible (D4, No look-ahead)."""
    session = _setup_sqlite_db()
    sec_id = uuid4()
    sec = Security(id=sec_id, company_name="Test Company", isin="INE000000001", is_active=True)
    session.add(sec)
    session.commit()

    # Q3 filing published on 2026-01-20
    records = [
        ParsedShareholdingRecord(
            quarter_end=date(2025, 12, 31),
            promoter_pct=60.0,
            promoter_pledged_pct_of_promoter=5.0,
            fii_pct=20.0,
            dii_pct=10.0,
            public_pct=10.0,
            published_at=datetime(2026, 1, 20, 10, 0, tzinfo=UTC),
        )
    ]
    ingest_shareholding_records(session, sec_id, records, datetime(2026, 1, 21, 0, 0, tzinfo=UTC))

    # Cutoff BEFORE publication date (2026-01-15): should NOT see the filing
    patterns_before = get_shareholding_as_of(
        session, sec_id, as_of=datetime(2026, 1, 15, 23, 59, tzinfo=UTC)
    )
    assert len(patterns_before) == 0

    # Cutoff AFTER publication date (2026-01-25): SHOULD see the filing
    patterns_after = get_shareholding_as_of(
        session, sec_id, as_of=datetime(2026, 1, 25, 23, 59, tzinfo=UTC)
    )
    assert len(patterns_after) == 1
    assert patterns_after[0]["quarter_end"] == date(2025, 12, 31)


def test_insider_trade_ingestion_and_deduplication() -> None:
    """Insider trades deduplicate on identical canonical content hash."""
    session = _setup_sqlite_db()
    sec_id = uuid4()
    sec = Security(id=sec_id, company_name="Test Company", isin="INE000000001", is_active=True)
    session.add(sec)
    session.commit()

    trades = [
        ParsedInsiderTradeRecord(
            person_category="Director",
            txn_type="sell",
            quantity=5000,
            value=2500000.0,
            txn_date=date(2025, 11, 15),
            published_at=datetime(2025, 11, 16, 9, 0, tzinfo=UTC),
        )
    ]

    res1 = ingest_insider_trade_records(
        session, sec_id, trades, datetime(2025, 11, 17, 0, 0, tzinfo=UTC)
    )
    assert res1["inserted"] == 1
    assert res1["skipped_duplicate"] == 0

    res2 = ingest_insider_trade_records(
        session, sec_id, trades, datetime(2025, 11, 17, 0, 0, tzinfo=UTC)
    )
    assert res2["inserted"] == 0
    assert res2["skipped_duplicate"] == 1
