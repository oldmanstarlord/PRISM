"""Governance ingestion service — deduplication, persistence, and querying.

Key design rules:
  - Duplicate disclosures: deduplicated by content_hash (SHA-256 of canonical fields).
  - Restatements: stored as new rows with version > 1 (D4, never overwrite).
  - Point-in-time reads: all queries accept published_at <= as_of cutoff (D4).
  - Idempotent: re-ingesting the same content produces no new rows (D6).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    InsiderTrade,
    Security,
    SecurityAlias,
    ShareholdingPattern,
)
from backend.app.governance.adapters.base import (
    ParsedInsiderTradeRecord,
    ParsedShareholdingRecord,
)
from backend.app.governance.config import GovernanceAnalysisConfig
from backend.app.governance.metrics import (
    compute_insider_activity,
    compute_institutional_flow,
    compute_pledge_metrics,
)

# ---------------------------------------------------------------------------
# Content hash helpers
# ---------------------------------------------------------------------------


def _shareholding_content_hash(
    security_id: UUID,
    quarter_end: date,
    promoter_pct: float | None,
    promoter_pledged_pct_of_promoter: float | None,
    fii_pct: float | None,
    dii_pct: float | None,
    public_pct: float | None,
    published_at: datetime,
) -> str:
    """Deterministic SHA-256 for shareholding deduplication."""
    payload = {
        "security_id": str(security_id),
        "quarter_end": quarter_end.isoformat(),
        "promoter_pct": promoter_pct,
        "promoter_pledged_pct_of_promoter": promoter_pledged_pct_of_promoter,
        "fii_pct": fii_pct,
        "dii_pct": dii_pct,
        "public_pct": public_pct,
        "published_at": published_at.isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _insider_content_hash(
    security_id: UUID,
    person_category: str,
    txn_type: str,
    quantity: int | None,
    txn_date: date,
    published_at: datetime,
) -> str:
    """Deterministic SHA-256 for insider trade deduplication."""
    payload = {
        "security_id": str(security_id),
        "person_category": person_category,
        "txn_type": txn_type,
        "quantity": quantity,
        "txn_date": txn_date.isoformat(),
        "published_at": published_at.isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Security resolution
# ---------------------------------------------------------------------------


def _resolve_security(session: Session, symbol: str) -> Security | None:
    alias = session.scalars(
        select(SecurityAlias).where(SecurityAlias.symbol == symbol.strip().upper())
    ).first()
    if alias is None:
        return None
    return session.get(Security, alias.security_id)


# ---------------------------------------------------------------------------
# Shareholding ingestion
# ---------------------------------------------------------------------------


def ingest_shareholding_records(
    session: Session,
    security_id: UUID,
    records: list[ParsedShareholdingRecord],
    ingested_at: datetime,
    source_document_id: UUID | None = None,
) -> dict[str, int]:
    """Persist shareholding records idempotently.

    For each record:
    1. Compute content_hash.
    2. If hash already exists → skip (idempotent).
    3. Determine version: max(existing version for same quarter) + 1.
    4. Insert new row.

    Returns counts: {"inserted": N, "skipped_duplicate": M}
    """
    now_utc = ingested_at
    inserted = 0
    skipped = 0

    for rec in records:
        ch = _shareholding_content_hash(
            security_id=security_id,
            quarter_end=rec.quarter_end,
            promoter_pct=rec.promoter_pct,
            promoter_pledged_pct_of_promoter=rec.promoter_pledged_pct_of_promoter,
            fii_pct=rec.fii_pct,
            dii_pct=rec.dii_pct,
            public_pct=rec.public_pct,
            published_at=rec.published_at,
        )
        existing = session.scalar(
            select(ShareholdingPattern).where(ShareholdingPattern.content_hash == ch)
        )
        if existing is not None:
            skipped += 1
            continue

        # Determine version (restatement support)
        existing_max_version = session.scalar(
            select(ShareholdingPattern.version)
            .where(
                ShareholdingPattern.security_id == security_id,
                ShareholdingPattern.quarter_end == rec.quarter_end,
            )
            .order_by(ShareholdingPattern.version.desc())
            .limit(1)
        )
        version = (existing_max_version or 0) + 1

        row = ShareholdingPattern(
            security_id=security_id,
            quarter_end=rec.quarter_end,
            promoter_pct=rec.promoter_pct,
            promoter_pledged_pct_of_promoter=rec.promoter_pledged_pct_of_promoter,
            fii_pct=rec.fii_pct,
            dii_pct=rec.dii_pct,
            public_pct=rec.public_pct,
            published_at=rec.published_at,
            ingested_at=now_utc,
            source_document_id=source_document_id,
            source=rec.source,
            content_hash=ch,
            version=version,
        )
        session.add(row)
        inserted += 1

    session.flush()
    return {"inserted": inserted, "skipped_duplicate": skipped}


# ---------------------------------------------------------------------------
# Insider trade ingestion
# ---------------------------------------------------------------------------


def ingest_insider_trade_records(
    session: Session,
    security_id: UUID,
    records: list[ParsedInsiderTradeRecord],
    ingested_at: datetime,
    source_document_id: UUID | None = None,
) -> dict[str, int]:
    """Persist insider trade records idempotently (deduplicated by content_hash)."""
    inserted = 0
    skipped = 0

    for rec in records:
        ch = _insider_content_hash(
            security_id=security_id,
            person_category=rec.person_category,
            txn_type=rec.txn_type,
            quantity=rec.quantity,
            txn_date=rec.txn_date,
            published_at=rec.published_at,
        )
        existing = session.scalar(select(InsiderTrade).where(InsiderTrade.content_hash == ch))
        if existing is not None:
            skipped += 1
            continue

        row = InsiderTrade(
            security_id=security_id,
            person_category=rec.person_category,
            txn_type=rec.txn_type,
            quantity=rec.quantity,
            value=rec.value,
            txn_date=rec.txn_date,
            published_at=rec.published_at,
            ingested_at=ingested_at,
            source_document_id=source_document_id,
            source=rec.source,
            content_hash=ch,
        )
        session.add(row)
        inserted += 1

    session.flush()
    return {"inserted": inserted, "skipped_duplicate": skipped}


# ---------------------------------------------------------------------------
# Point-in-time read helpers
# ---------------------------------------------------------------------------


def get_shareholding_as_of(
    session: Session,
    security_id: UUID,
    as_of: datetime,
) -> list[dict[str, Any]]:
    """Return all shareholding pattern rows for security with published_at <= as_of.

    Results are not further filtered — callers choose the lookback.
    """
    rows = session.scalars(
        select(ShareholdingPattern)
        .where(
            ShareholdingPattern.security_id == security_id,
            ShareholdingPattern.published_at <= as_of,
        )
        .order_by(ShareholdingPattern.quarter_end, ShareholdingPattern.version)
    ).all()
    return [
        {
            "id": str(row.id),
            "quarter_end": row.quarter_end,
            "promoter_pct": row.promoter_pct,
            "promoter_pledged_pct_of_promoter": row.promoter_pledged_pct_of_promoter,
            "fii_pct": row.fii_pct,
            "dii_pct": row.dii_pct,
            "public_pct": row.public_pct,
            "published_at": row.published_at,
            "version": row.version,
            "source": row.source,
        }
        for row in rows
    ]


def get_insider_trades_as_of(
    session: Session,
    security_id: UUID,
    as_of: datetime,
) -> list[dict[str, Any]]:
    """Return all insider trades for security with published_at <= as_of."""
    rows = session.scalars(
        select(InsiderTrade)
        .where(
            InsiderTrade.security_id == security_id,
            InsiderTrade.published_at <= as_of,
        )
        .order_by(InsiderTrade.txn_date.desc(), InsiderTrade.published_at.desc())
    ).all()
    return [
        {
            "id": str(row.id),
            "person_category": row.person_category,
            "txn_type": row.txn_type,
            "quantity": row.quantity,
            "value": row.value,
            "txn_date": row.txn_date,
            "published_at": row.published_at,
            "source": row.source,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Governance signal service
# ---------------------------------------------------------------------------


def get_governance_signals(
    session: Session,
    symbol: str,
    as_of: datetime | None = None,
    config: GovernanceAnalysisConfig | None = None,
    market_cap_inr: float | None = None,
) -> dict[str, Any] | None:
    """Build the full governance signal payload for a stock.

    Parameters
    ----------
    session:    DB session.
    symbol:     NSE symbol (resolved via security_alias).
    as_of:      Effective datetime for point-in-time filtering.
    config:     Governance analysis config; defaults to class defaults.
    market_cap_inr: Current market cap in INR for insider ratio; optional.

    Returns None if the security is not found.
    """
    from datetime import UTC

    norm = symbol.strip().upper()
    now_utc = as_of or datetime.now(UTC)
    cfg = config or GovernanceAnalysisConfig()

    security = _resolve_security(session, norm)
    if security is None:
        return None

    # --- Shareholding data (point-in-time) ---
    patterns = get_shareholding_as_of(session, security.id, now_utc)
    pledge_m = compute_pledge_metrics(patterns, cfg)
    inst_m = compute_institutional_flow(patterns, cfg)

    # --- Insider trades (point-in-time) ---
    trades = get_insider_trades_as_of(session, security.id, now_utc)
    insider_m = compute_insider_activity(trades, now_utc.date(), market_cap_inr, cfg)

    # Build holding table (most recent N quarters, de-versioned)
    holding_table = _build_holding_table(patterns)

    return {
        "symbol": norm,
        "company_name": security.company_name,
        "as_of": now_utc.date().isoformat(),
        "pledge": {
            "quarter_end": pledge_m.quarter_end.isoformat()
            if pledge_m.quarter_end != date.min
            else None,
            "pledge_level_pct": pledge_m.pledge_level,
            "pledge_change_pct": pledge_m.pledge_change,
            "n_quarters_available": pledge_m.n_quarters_available,
            "status": pledge_m.status,
            "limitations": pledge_m.limitations,
        },
        "promoter_holding": {
            "promoter_pct": pledge_m.promoter_pct,
            "promoter_change_pct": pledge_m.promoter_change,
            "status": pledge_m.status,
        },
        "institutional_flow": {
            "quarter_end": inst_m.quarter_end.isoformat()
            if inst_m.quarter_end != date.min
            else None,
            "fii_pct": inst_m.fii_pct,
            "dii_pct": inst_m.dii_pct,
            "combined_pct": inst_m.combined_pct,
            "institutional_change_pct": inst_m.institutional_change,
            "n_quarters_available": inst_m.n_quarters_available,
            "status": inst_m.status,
            "limitations": inst_m.limitations,
        },
        "insider_activity": {
            "window_days": insider_m.window_days,
            "window_start": insider_m.window_start.isoformat(),
            "window_end": insider_m.window_end.isoformat(),
            "buy_value_inr": insider_m.buy_value,
            "sell_value_inr": insider_m.sell_value,
            "net_sell_value_inr": insider_m.net_sell_value,
            "trade_count": insider_m.trade_count,
            "insider_sell_ratio": insider_m.insider_sell_ratio,
            "status": insider_m.status,
            "limitations": insider_m.limitations,
        },
        "holding_table": holding_table,
        "recent_insider_trades": _build_trade_list(trades, cfg.insider_window_days, now_utc.date()),
        "limitations": [
            "Governance signals are descriptive and do not predict future price movements.",
            "Shareholding data from SEBI Reg 31 quarterly filings (21-day disclosure lag).",
            "Insider trade data from SEBI PIT Reg 7(2) and SAST Reg 29/31 filings.",
            "MST/correlation is never presented as causal.",
        ],
        "method_version": "governance_analysis_v1",
        "config_key": "governance_analysis",
    }


def _build_holding_table(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return de-versioned holding history (latest version per quarter), newest first."""
    by_quarter: dict[date, dict[str, Any]] = {}
    for p in patterns:
        q: date = p["quarter_end"]
        if q not in by_quarter or p["version"] > by_quarter[q]["version"]:
            by_quarter[q] = p
    rows = sorted(by_quarter.values(), key=lambda r: r["quarter_end"], reverse=True)
    return [
        {
            "quarter_end": r["quarter_end"].isoformat(),
            "promoter_pct": r["promoter_pct"],
            "promoter_pledged_pct_of_promoter": r["promoter_pledged_pct_of_promoter"],
            "fii_pct": r["fii_pct"],
            "dii_pct": r["dii_pct"],
            "public_pct": r["public_pct"],
            "published_at": r["published_at"].isoformat(),
            "source": r["source"],
        }
        for r in rows
    ]


def _build_trade_list(
    trades: list[dict[str, Any]],
    window_days: int,
    as_of: date,
) -> list[dict[str, Any]]:
    """Return the most recent trades sorted newest-first (up to 20 rows)."""
    from datetime import timedelta

    cutoff = as_of - timedelta(days=window_days)
    recent = [t for t in trades if t["txn_date"] >= cutoff]
    recent_sorted = sorted(recent, key=lambda t: t["txn_date"], reverse=True)[:20]
    return [
        {
            "person_category": t["person_category"],
            "txn_type": t["txn_type"],
            "quantity": t["quantity"],
            "value_inr": t["value"],
            "txn_date": t["txn_date"].isoformat(),
            "published_at": t["published_at"].isoformat(),
            "source": t["source"],
        }
        for t in recent_sorted
    ]
