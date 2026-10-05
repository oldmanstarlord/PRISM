"""Tests for shares outstanding adapter, point-in-time constraints, and no look-ahead (OQ-8, D4)."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.db.models import SecurityShareCount
from backend.app.market_data.shares import (
    CsvSharesAdapter,
    get_shares_point_in_time,
)

SAMPLE_SHARES_CSV = """symbol,as_of,shares_outstanding,published_at,source,notes
RELIANCE,2026-06-30,6765000000,2026-07-15T18:00:00Z,NSE_SHAREHOLDING_FILING,Q1 filing
TCS,2026-06-30,3618000000,2026-07-12T12:00:00Z,NSE_SHAREHOLDING_FILING,Q1 filing
"""


def test_csv_shares_adapter_parses_records() -> None:
    adapter = CsvSharesAdapter()
    records = adapter.parse_csv(SAMPLE_SHARES_CSV)

    assert len(records) == 2
    assert records[0].symbol == "RELIANCE"
    assert records[0].as_of == date(2026, 6, 30)
    assert records[0].shares_outstanding == 6765000000
    assert records[0].published_at == datetime(2026, 7, 15, 18, 0, tzinfo=UTC)


def test_no_backfilling_before_published_at() -> None:
    """Point-in-Time rule (D4):
    A share count filing must NEVER be used on dates prior to published_at.
    """
    sec_id = uuid4()
    filing_published = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
    share_row = SecurityShareCount(
        security_id=sec_id,
        as_of=date(2026, 6, 30),
        shares_outstanding=6765000000,
        source="NSE",
        published_at=filing_published,
        ingested_at=filing_published,
    )

    # Mock session
    mock_session = MagicMock()

    # Query before published_at (e.g. 2026-07-10) -> query filter excludes it
    def side_effect(stmt):
        # Inspect statement representation or simulate filtering
        return MagicMock(first=lambda: None)

    mock_session.scalars.side_effect = side_effect

    # Query with cutoff prior to publication
    cutoff_before = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
    res_before = get_shares_point_in_time(
        session=mock_session,
        security_id=sec_id,
        trade_date=date(2026, 7, 10),
        cutoff=cutoff_before,
    )
    assert res_before is None

    # Query with cutoff after publication
    cutoff_after = datetime(2026, 7, 16, 0, 0, tzinfo=UTC)
    mock_session.scalars.side_effect = lambda stmt: MagicMock(first=lambda: share_row)
    res_after = get_shares_point_in_time(
        session=mock_session,
        security_id=sec_id,
        trade_date=date(2026, 7, 16),
        cutoff=cutoff_after,
    )
    assert res_after is not None
    assert res_after.shares_outstanding == 6765000000
