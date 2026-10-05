"""Shares outstanding adapter interface, CSV import, and point-in-time retrieval (OQ-8, D4)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Security, SecurityAlias, SecurityShareCount


@dataclass(frozen=True, slots=True)
class ShareCountRecord:
    """Share count observation with publication timestamp."""

    symbol: str
    as_of: date
    shares_outstanding: int
    published_at: datetime
    source: str
    notes: str | None = None


@runtime_checkable
class SharesAdapter(Protocol):
    """Replaceable adapter interface for security shares outstanding (FR-D9)."""

    def fetch_shares(self, symbol: str, as_of: date) -> ShareCountRecord | None:
        """Fetch point-in-time share count observation."""
        ...


class CsvSharesAdapter:
    """CSV importer for point-in-time shares outstanding.

    Supports official quarterly shareholding patterns filed with NSE/BSE.
    Enforces publication date constraints: never uses shares before published_at.
    """

    def parse_csv(self, csv_content: str | io.StringIO) -> list[ShareCountRecord]:
        """Parse CSV with columns:
        symbol, as_of, shares_outstanding, published_at, source, notes.
        """
        if isinstance(csv_content, str):
            f = io.StringIO(csv_content)
        else:
            f = csv_content

        reader = csv.DictReader(f)
        records: list[ShareCountRecord] = []

        for row in reader:
            normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            symbol = normalized.get("symbol")
            as_of_str = normalized.get("as_of")
            shares_str = normalized.get("shares_outstanding") or normalized.get("shares")
            pub_str = normalized.get("published_at") or normalized.get("publication_date")
            source = normalized.get("source", "NSE_SHAREHOLDING_FILING")
            notes = normalized.get("notes")

            if not (symbol and as_of_str and shares_str and pub_str):
                continue

            try:
                as_of = date.fromisoformat(as_of_str)
                shares = int(shares_str.replace(",", ""))
                if shares <= 0:
                    continue
                # Handle publication timestamp with timezone
                if "T" in pub_str:
                    published_at = datetime.fromisoformat(pub_str)
                else:
                    published_at = datetime.strptime(pub_str, "%Y-%m-%d").replace(tzinfo=UTC)
            except Exception:
                continue

            records.append(
                ShareCountRecord(
                    symbol=symbol.upper(),
                    as_of=as_of,
                    shares_outstanding=shares,
                    published_at=published_at,
                    source=source,
                    notes=notes,
                )
            )

        return records


def persist_share_counts(
    session: Session,
    records: list[ShareCountRecord],
) -> tuple[int, int]:
    """Idempotently persist share counts mapped by symbol to security_id."""
    if not records:
        return 0, 0

    now = datetime.now(UTC)
    inserted = 0
    skipped = 0

    # Build symbol -> security_id map
    alias_rows = session.execute(select(SecurityAlias.symbol, SecurityAlias.security_id)).all()
    symbol_map = {row[0].upper(): row[1] for row in alias_rows}

    for rec in records:
        sec_id = symbol_map.get(rec.symbol)
        if sec_id is None:
            # Fallback to direct symbol lookup if needed
            sec_id = session.scalar(select(Security.id).where(Security.isin == rec.symbol))
            if sec_id is None:
                skipped += 1
                continue

        # Check existing row
        existing = session.scalar(
            select(SecurityShareCount).where(
                SecurityShareCount.security_id == sec_id,
                SecurityShareCount.as_of == rec.as_of,
                SecurityShareCount.source == rec.source,
            )
        )
        if existing is not None:
            skipped += 1
            continue

        row = SecurityShareCount(
            security_id=sec_id,
            as_of=rec.as_of,
            shares_outstanding=rec.shares_outstanding,
            source=rec.source,
            published_at=rec.published_at,
            ingested_at=now,
            notes=rec.notes,
        )
        session.add(row)
        inserted += 1

    session.flush()
    return inserted, skipped


def get_shares_point_in_time(
    session: Session,
    security_id: UUID,
    trade_date: date,
    cutoff: datetime | None = None,
) -> SecurityShareCount | None:
    """Retrieve the most recent share count known on or before trade_date and cutoff.

    Point-in-Time Rule (D4):
    Never back-fill earlier than published_at. Only share records with
    published_at <= cutoff AND as_of <= trade_date are eligible.
    """
    stmt = (
        select(SecurityShareCount)
        .where(
            SecurityShareCount.security_id == security_id,
            SecurityShareCount.as_of <= trade_date,
        )
        .order_by(SecurityShareCount.as_of.desc())
    )
    if cutoff is not None:
        stmt = stmt.where(SecurityShareCount.published_at <= cutoff)

    return session.scalars(stmt).first()
