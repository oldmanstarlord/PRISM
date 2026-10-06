"""Strict source-adapter tests: schema, PIT, missing file, and bad rows."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.events.adapters.csv_adapter import NseAnnouncementCsvAdapter
from backend.app.governance.adapters.csv_adapter import (
    CsvInsiderTradeAdapter,
    CsvShareholdingAdapter,
)
from backend.app.policy.adapters.rss_adapter import RssNewsAdapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"


def test_official_announcement_export_is_strict_and_deterministic() -> None:
    adapter = NseAnnouncementCsvAdapter(FIXTURES / "nse_announcements.csv")
    first = adapter.fetch_announcements()
    second = adapter.fetch_announcements()
    assert first == second
    assert first[0].symbol == "TEST"
    assert first[0].source_doc_id == second[0].source_doc_id
    assert first[0].published_at == datetime(2026, 10, 5, 12, 45, tzinfo=UTC)


def test_missing_announcement_file_fails_loudly_before_any_write(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="export not found"):
        NseAnnouncementCsvAdapter(tmp_path / "missing.csv").fetch_announcements()


def test_shareholding_validates_percentages_quarter_and_real_share_count() -> None:
    records = (
        CsvShareholdingAdapter(file_path=str(FIXTURES / "nse_shareholding.csv"))
        .fetch_shareholding("TEST")[0]
        .records
    )
    assert records[0].shares_outstanding == 100_000_000
    assert records[0].source == "NSE_MANUAL_IMPORT"
    bad = (
        "symbol,quarter_end,promoter_pct,promoter_pledged_pct_of_promoter,"
        "fii_pct,dii_pct,public_pct,published_at\n"
        "TEST,2026-05-31,101,2,10,10,10,2026-06-01T00:00:00+0000\n"
    )
    with pytest.raises(ValueError, match="row 2"):
        CsvShareholdingAdapter(csv_text=bad).fetch_shareholding("TEST")


def test_shareholding_point_in_time_filter_and_insider_schema() -> None:
    share_adapter = CsvShareholdingAdapter(file_path=str(FIXTURES / "nse_shareholding.csv"))
    hidden = share_adapter.fetch_shareholding(
        "TEST", as_of=datetime(2026, 7, 14, 23, 59, tzinfo=UTC)
    )[0].records
    assert hidden == []
    trades = (
        CsvInsiderTradeAdapter(file_path=str(FIXTURES / "nse_insider_trades.csv"))
        .fetch_trades("TEST")[0]
        .records
    )
    assert trades[0].quantity == 1000
    assert trades[0].source == "NSE_MANUAL_IMPORT"


def test_bad_governance_header_and_missing_file_fail_loudly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        CsvInsiderTradeAdapter(csv_text="symbol,txn_type\nTEST,buy\n").fetch_trades("TEST")
    with pytest.raises(FileNotFoundError, match="export not found"):
        CsvShareholdingAdapter(file_path=str(tmp_path / "absent.csv")).fetch_shareholding("TEST")


def test_rss_metadata_only_and_empty_feed_failure() -> None:
    xml = b"""<rss><channel><item><title>Policy circular</title>
    <link>https://www.sebi.gov.in/example</link>
    <pubDate>Mon, 05 Oct 2026 09:00:00 +0530</pubDate>
    <description>Body text that must not be stored.</description></item></channel></rss>"""

    class Response:
        content = xml

        @staticmethod
        def raise_for_status() -> None:
            return None

    adapter = RssNewsAdapter(rss_url="https://example.invalid/feed")
    adapter.session.get = lambda *_args, **_kwargs: Response()  # type: ignore[method-assign]
    rows = adapter.fetch_news()
    assert rows[0].headline == "Policy circular"
    assert not hasattr(rows[0], "body")

    Response.content = b"<rss><channel /></rss>"
    with pytest.raises(RuntimeError, match="every configured RSS feed failed"):
        adapter.fetch_news()
