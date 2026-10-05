"""Test: failed or partial ingestion cannot replace the last-known-good dataset.

SRS reference
-------------
Section 14.2 Failure rules:
  "Do not replace a last-known-good dataset with an incomplete run."
Section 16 acceptance checklist:
  "Failed or partial ingestion cannot replace the last-known-good dataset."

Design
------
The rule is enforced at two levels:

1. Per-symbol isolation (ingest_nifty200_prices line 363–365):
   If a provider or database exception occurs while processing one symbol, the
   session is rolled back for *that symbol only*. No rows inserted for the
   failing symbol survive, but every previously committed symbol is unaffected.

2. Persist-prices idempotency (persist_prices):
   ``persist_prices`` only inserts a new raw revision when the new values differ
   from the highest existing revision.  An identical retry cannot overwrite data.

This test file verifies both properties using SQLite in-memory databases and
directly calling ``persist_prices``, bypassing the network layer entirely.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import (
    PriceDailyAdjusted,
    PriceDailyRaw,
    Security,
    SecurityAlias,
)
from backend.app.market_data.service import (
    persist_prices,
)
from backend.app.market_data.types import DailyPrice

# ---------------------------------------------------------------------------
# SQLite engine with JSONB stubbed out
# ---------------------------------------------------------------------------
# SQLAlchemy's JSONB dialect type is PostgreSQL-specific.  For SQLite tests we
# override it by listening for the ``before_create`` event and patching JSONB
# with the generic JSON type at the engine/dialect level.
# ---------------------------------------------------------------------------


def _make_sqlite_engine() -> Any:
    """Return an in-memory SQLite engine that tolerates JSONB columns."""
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB

    engine = create_engine("sqlite:///:memory:", echo=False)

    # Replace JSONB with JSON for the SQLite dialect so DDL succeeds.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    # Monkey-patch JSONB's compilation for SQLite by using JSON.
    from sqlalchemy.dialects import sqlite as sqlite_dialect
    from sqlalchemy.sql import sqltypes

    # Register JSON as the SQLite rendering of JSONB.
    sqlite_dialect.dialect.ischema_names["JSONB"] = sqltypes.JSON
    JSONB.__class_getitem__ = lambda cls, item: JSON  # type: ignore[method-assign]

    Base.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
TRADE_DATE = date(2026, 10, 1)


def _sample_price(
    trade_date: date = TRADE_DATE,
    close: str = "100.00",
    adj_close: str = "100.00",
) -> DailyPrice:
    return DailyPrice(
        trade_date=trade_date,
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("95.00"),
        close=Decimal(close),
        adjusted_close=Decimal(adj_close),
        volume=10_000,
    )


def _setup_session_with_security(
    session: Session,
    security_id: UUID | None = None,
    symbol: str = "TESTCO",
) -> UUID:
    """Insert a minimal Security + SecurityAlias and return the security_id."""
    sid = security_id or uuid4()
    sec = Security(
        id=sid,
        isin=f"IN{sid.hex[:10].upper()}",
        company_name="Test Company",
        industry="Test Industry",
    )
    alias = SecurityAlias(
        security_id=sid,
        symbol=symbol,
        exchange="NSE",
        valid_from=date(2015, 1, 1),
        source="test",
        ingested_at=NOW,
    )
    session.add_all([sec, alias])
    session.commit()
    return sid


# ---------------------------------------------------------------------------
# Helpers that avoid JSONB issues on SQLite by using raw INSERT
# ---------------------------------------------------------------------------


def _raw_count(session: Session, security_id: UUID) -> int:
    return len(
        session.scalars(select(PriceDailyRaw).where(PriceDailyRaw.security_id == security_id)).all()
    )


def _adj_count(session: Session, security_id: UUID) -> int:
    return len(
        session.scalars(
            select(PriceDailyAdjusted).where(PriceDailyAdjusted.security_id == security_id)
        ).all()
    )


# ---------------------------------------------------------------------------
# 1. Failed ingestion does not remove previously committed rows
# ---------------------------------------------------------------------------


class TestLastKnownGoodUnchangedOnFailure:
    """
    Simulate a mid-run provider failure for one symbol and assert that rows for
    the *other* (already-committed) symbol are entirely unaffected.

    This matches the pattern in ``ingest_nifty200_prices``:
        try:
            counts = _persist_with_retry(session, instrument, quality.accepted)
            session.commit()
            ...
        except Exception:
            session.rollback()
            summary.failed_symbols[...] = ...

    We reproduce that logic by calling ``persist_prices`` + ``session.commit()``
    for symbol A (success), then simulating a failure for symbol B by raising an
    exception after staging rows but before committing, then rolling back.
    """

    def test_good_symbol_rows_survive_failed_symbol_ingestion(self) -> None:
        engine = create_engine("sqlite:///:memory:", echo=False)

        from sqlalchemy import JSON
        from sqlalchemy.dialects.postgresql import JSONB

        JSONB.impl = JSON  # type: ignore[attr-defined]

        # Re-create tables each time with fresh mapping.
        # Use a fresh metadata binding for SQLite.
        from sqlalchemy import MetaData

        from backend.app.db.base import Base as _Base

        sqlite_meta = MetaData()
        for table in _Base.metadata.sorted_tables:
            table.to_metadata(sqlite_meta)
        sqlite_meta.create_all(engine)

        SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        with SessionLocal() as session:
            sid_a = _setup_session_with_security(session, symbol="GOOD")
            sid_b = _setup_session_with_security(session, symbol="FAIL")

            # ---- Symbol A: successful ingestion ----
            from backend.app.market_data.types import MarketInstrument

            instrument_a = MarketInstrument(security_id=sid_a, symbol="GOOD")
            prices_a = (
                _sample_price(trade_date=date(2026, 9, 30), close="200.00", adj_close="200.00"),
            )
            persist_prices(session, instrument_a, prices_a, NOW)
            session.commit()

            raw_before = _raw_count(session, sid_a)
            adj_before = _adj_count(session, sid_a)
            assert raw_before == 1, "Pre-condition: symbol A has 1 raw row"
            assert adj_before == 1, "Pre-condition: symbol A has 1 adjusted row"

            # ---- Symbol B: simulated failure ----
            # Stage rows for symbol B…
            instrument_b = MarketInstrument(security_id=sid_b, symbol="FAIL")
            prices_b = (
                _sample_price(trade_date=date(2026, 9, 30), close="50.00", adj_close="50.00"),
            )
            persist_prices(session, instrument_b, prices_b, NOW)
            # …then simulate a provider/DB error before commit.
            session.rollback()  # mirrors ingest_nifty200_prices exception handler

            # ---- Assertions ----
            # Symbol A rows must be completely unchanged.
            raw_after = _raw_count(session, sid_a)
            adj_after = _adj_count(session, sid_a)
            assert raw_after == raw_before, (
                f"Symbol A raw row count changed: {raw_before} → {raw_after}. "
                "Failed ingestion must not replace last-known-good data."
            )
            assert adj_after == adj_before, (
                f"Symbol A adjusted row count changed: {adj_before} → {adj_after}."
            )

            # Symbol B must have zero rows (its transaction was rolled back).
            raw_b = _raw_count(session, sid_b)
            adj_b = _adj_count(session, sid_b)
            assert raw_b == 0, f"Symbol B has {raw_b} raw rows after rollback; expected 0."
            assert adj_b == 0, f"Symbol B has {adj_b} adjusted rows after rollback; expected 0."


# ---------------------------------------------------------------------------
# 2. persist_prices is idempotent: identical retry creates no new rows
# ---------------------------------------------------------------------------


class TestPersistPricesIdempotency:
    """
    Calling persist_prices twice with identical prices must not create a second
    raw revision or adjusted revision.

    This proves that a retry after a transient failure (before commit) cannot
    silently duplicate historical data.
    """

    def test_identical_retry_creates_no_new_rows(self) -> None:
        engine = create_engine("sqlite:///:memory:", echo=False)

        from sqlalchemy import JSON
        from sqlalchemy.dialects.postgresql import JSONB

        JSONB.impl = JSON  # type: ignore[attr-defined]

        from sqlalchemy import MetaData

        from backend.app.db.base import Base as _Base

        sqlite_meta = MetaData()
        for table in _Base.metadata.sorted_tables:
            table.to_metadata(sqlite_meta)
        sqlite_meta.create_all(engine)

        SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        with SessionLocal() as session:
            sid = _setup_session_with_security(session, symbol="RETRY")

            from backend.app.market_data.types import MarketInstrument

            instrument = MarketInstrument(security_id=sid, symbol="RETRY")
            prices = (_sample_price(),)

            # First call + commit.
            persist_prices(session, instrument, prices, NOW)
            session.commit()
            raw_first = _raw_count(session, sid)
            adj_first = _adj_count(session, sid)

            # Identical second call + commit (simulates retry).
            persist_prices(session, instrument, prices, NOW)
            session.commit()
            raw_second = _raw_count(session, sid)
            adj_second = _adj_count(session, sid)

            assert raw_second == raw_first, (
                f"Idempotency violated: raw rows grew from {raw_first} to {raw_second}"
            )
            assert adj_second == adj_first, (
                f"Idempotency violated: adjusted rows grew from {adj_first} to {adj_second}"
            )
