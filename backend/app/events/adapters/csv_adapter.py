"""Strict importer for a manually downloaded official NSE announcement CSV."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.app.events.adapters.base import RawAnnouncement

_HEADER_ALIASES = {
    "symbol": ("SYMBOL", "Symbol", "symbol"),
    "company_name": ("COMPANY NAME", "Company Name", "company_name"),
    "headline": ("SUBJECT", "Subject", "headline"),
    "published_at": (
        "BROADCAST DATE/TIME",
        "Broadcast Date/Time",
        "published_at",
    ),
    "source_category": ("CATEGORY", "Category", "source_category", "SUBJECT"),
    "url": ("ATTACHMENT", "Attachment", "url"),
    "isin": ("ISIN", "isin"),
    "body": ("DETAILS", "Details", "body"),
}

_NSE_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _column(fieldnames: Sequence[str], logical_name: str, *, required: bool) -> str | None:
    for candidate in _HEADER_ALIASES[logical_name]:
        if candidate in fieldnames:
            return candidate
    if required:
        raise ValueError(
            f"announcement CSV is missing {logical_name!r}; accepted headers: "
            f"{', '.join(_HEADER_ALIASES[logical_name])}"
        )
    return None


def _parse_published_at(value: str) -> datetime:
    clean = value.strip()
    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
    ):
        try:
            parsed = datetime.strptime(clean, fmt)
            # NSE's official export displays naive broadcast times in Indian
            # Standard Time. Persist UTC while retaining actual-source semantics.
            return (
                parsed.astimezone(UTC)
                if parsed.tzinfo
                else parsed.replace(tzinfo=_NSE_TIMEZONE).astimezone(UTC)
            )
        except ValueError:
            continue
    raise ValueError(f"unreadable broadcast timestamp: {value!r}")


class NseAnnouncementCsvAdapter:
    """Parse all rows before persistence so a bad export cannot partially write."""

    source_key = "announcements_nse_manual"
    source_label = "NSE_MANUAL_IMPORT"

    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path)

    def fetch_announcements(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawAnnouncement]:
        if not self.file_path.is_file():
            raise FileNotFoundError(f"announcement export not found: {self.file_path}")
        with self.file_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            columns = {
                "symbol": _column(fieldnames, "symbol", required=True),
                "company_name": _column(fieldnames, "company_name", required=True),
                "headline": _column(fieldnames, "headline", required=True),
                "published_at": _column(fieldnames, "published_at", required=True),
                "source_category": _column(fieldnames, "source_category", required=True),
                "url": _column(fieldnames, "url", required=False),
                "isin": _column(fieldnames, "isin", required=False),
                "body": _column(fieldnames, "body", required=False),
            }
            output: list[RawAnnouncement] = []
            for row_number, row in enumerate(reader, start=2):
                try:
                    symbol = row[columns["symbol"]].strip().upper()
                    company = row[columns["company_name"]].strip()
                    headline = row[columns["headline"]].strip()
                    published_at = _parse_published_at(row[columns["published_at"]])
                    category = row[columns["source_category"]].strip()
                    if not symbol or not company or not headline or not category:
                        raise ValueError("symbol, company, subject and category must be non-empty")
                    if since and published_at < since:
                        continue
                    url = row.get(columns["url"], "").strip() if columns["url"] else None
                    isin = row.get(columns["isin"], "").strip() if columns["isin"] else None
                    body = row.get(columns["body"], "").strip() if columns["body"] else None
                    identity = "|".join((symbol, published_at.isoformat(), headline, url or ""))
                    output.append(
                        RawAnnouncement(
                            symbol=symbol,
                            company_name=company,
                            headline=headline,
                            source_category=category,
                            published_at=published_at,
                            source_doc_id=hashlib.sha256(identity.encode()).hexdigest(),
                            isin=isin or None,
                            body=body or None,
                            url=url or None,
                        )
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"announcement CSV row {row_number}: {exc}") from exc
        return output[:limit] if limit is not None else output
