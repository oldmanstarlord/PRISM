"""Cross-check engine comparing secondary feeds against official exchange records (NFR-9, D4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import DataCrosscheck, PriceDailyRaw, SecurityAlias

DEFAULT_TOLERANCE = Decimal("0.005")  # 0.5% tolerance threshold


@dataclass(frozen=True, slots=True)
class CrosscheckSummary:
    """Summary of cross-check results across sampled securities and dates."""

    run_id: UUID
    checked_at: datetime
    total_checked: int
    matches: int
    mismatches: int
    missing_comparison: int
    mismatch_rate: float
    tolerance: float
    worst_offenders: list[dict[str, Any]]


def run_price_crosscheck(
    session: Session,
    official_data: dict[tuple[str, date], Decimal],
    sample_dates: list[date] | None = None,
    tolerance: Decimal = DEFAULT_TOLERANCE,
    run_id: UUID | None = None,
) -> CrosscheckSummary:
    """Compare stored yfinance closing prices against official exchange daily close records.

    Rule: Never auto-correct prices. Record mismatches for audit and reporting only.
    """
    if run_id is None:
        run_id = uuid4()
    now = datetime.now(UTC)

    # Load symbol -> security_id map
    alias_rows = session.execute(select(SecurityAlias.symbol, SecurityAlias.security_id)).all()
    symbol_to_sec = {row[0].upper(): row[1] for row in alias_rows}
    sec_to_symbol = {sec_id: sym for sym, sec_id in symbol_to_sec.items()}

    # Query stored daily raw prices
    stmt = select(PriceDailyRaw)
    if sample_dates:
        stmt = stmt.where(PriceDailyRaw.trade_date.in_(sample_dates))

    raw_prices = session.scalars(stmt).all()

    total_checked = 0
    matches = 0
    mismatches = 0
    missing_b = 0
    offenders: list[dict[str, Any]] = []

    for price in raw_prices:
        sym = sec_to_symbol.get(price.security_id)
        if not sym:
            continue

        key = (sym, price.trade_date)
        if key not in official_data:
            missing_b += 1
            status = "missing_b"
            rel_diff = Decimal("1.0")
            close_b = Decimal("0.0")
        else:
            total_checked += 1
            close_b = official_data[key]
            close_a = price.close

            if close_b > 0:
                rel_diff = abs(close_a - close_b) / close_b
            else:
                rel_diff = Decimal("1.0")

            if rel_diff > tolerance:
                mismatches += 1
                status = "mismatch"
                offenders.append(
                    {
                        "symbol": sym,
                        "trade_date": price.trade_date.isoformat(),
                        "source_a": "yfinance",
                        "close_a": float(close_a),
                        "source_b": "official_exchange",
                        "close_b": float(close_b),
                        "rel_diff": float(rel_diff),
                    }
                )
            else:
                matches += 1
                status = "match"

        # Check existing row
        existing = session.scalar(
            select(DataCrosscheck).where(
                DataCrosscheck.run_id == run_id,
                DataCrosscheck.security_id == price.security_id,
                DataCrosscheck.trade_date == price.trade_date,
            )
        )
        if existing is None:
            check_row = DataCrosscheck(
                run_id=run_id,
                security_id=price.security_id,
                trade_date=price.trade_date,
                source_a="yfinance",
                source_b="official_exchange",
                close_a=price.close,
                close_b=close_b,
                rel_diff=rel_diff,
                status=status,
                details={"tolerance": float(tolerance)},
                checked_at=now,
            )
            session.add(check_row)

    session.flush()

    offenders.sort(key=lambda x: x["rel_diff"], reverse=True)
    mismatch_rate = (mismatches / total_checked) if total_checked > 0 else 0.0

    return CrosscheckSummary(
        run_id=run_id,
        checked_at=now,
        total_checked=total_checked,
        matches=matches,
        mismatches=mismatches,
        missing_comparison=missing_b,
        mismatch_rate=round(mismatch_rate, 4),
        tolerance=float(tolerance),
        worst_offenders=offenders[:10],
    )
