"""Derivation of traded value, 20-day ADV, point-in-time market cap, and liquidity flags."""

from __future__ import annotations

from collections import deque
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    PriceDailyRaw,
    Security,
    SecurityMarketStat,
)
from backend.app.market_data.shares import get_shares_point_in_time

# Thresholds
THIN_TRADING_VALUE_THRESHOLD = Decimal("1000000.00")  # Rs. 10 Lakhs daily traded value
ADV_WINDOW = 20
MIN_ADV_OBSERVATIONS = 10


def derive_security_market_stats(
    session: Session,
    security_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    cutoff: datetime | None = None,
) -> int:
    """Derive traded_value, adv_20, market_cap and liquidity flags for a security."""
    stmt = (
        select(PriceDailyRaw)
        .where(PriceDailyRaw.security_id == security_id)
        .order_by(PriceDailyRaw.trade_date.asc())
    )
    if start_date is not None:
        stmt = stmt.where(PriceDailyRaw.trade_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(PriceDailyRaw.trade_date <= end_date)
    if cutoff is not None:
        stmt = stmt.where(PriceDailyRaw.ingested_at <= cutoff)

    raw_prices = session.scalars(stmt).all()
    if not raw_prices:
        return 0

    # Load existing market stats dates to avoid duplicate work
    existing_dates = set(
        session.scalars(
            select(SecurityMarketStat.trade_date).where(
                SecurityMarketStat.security_id == security_id
            )
        ).all()
    )

    now = datetime.now(UTC)
    inserted_or_updated = 0
    recent_traded_values: deque[Decimal] = deque(maxlen=ADV_WINDOW)

    for price in raw_prices:
        close_dec = price.close
        vol = price.volume
        traded_val = close_dec * Decimal(vol)

        recent_traded_values.append(traded_val)

        # 20-day ADV
        if len(recent_traded_values) >= MIN_ADV_OBSERVATIONS:
            adv_20 = sum(recent_traded_values) / Decimal(len(recent_traded_values))
        else:
            adv_20 = None

        # Point-in-time shares and market cap
        shares_rec = get_shares_point_in_time(
            session=session,
            security_id=security_id,
            trade_date=price.trade_date,
            cutoff=cutoff,
        )
        if shares_rec is not None:
            market_cap = Decimal(shares_rec.shares_outstanding) * close_dec
            shares_used = shares_rec.shares_outstanding
            shares_as_of = shares_rec.as_of
        else:
            market_cap = None
            shares_used = None
            shares_as_of = None

        # Flags
        flags: dict[str, object] = {}
        if vol == 0:
            flags["zero_volume"] = True
        if traded_val < THIN_TRADING_VALUE_THRESHOLD:
            flags["thin_trading"] = True

        if price.trade_date in existing_dates:
            # Update existing
            existing_stat = session.scalar(
                select(SecurityMarketStat).where(
                    SecurityMarketStat.security_id == security_id,
                    SecurityMarketStat.trade_date == price.trade_date,
                )
            )
            if existing_stat is not None:
                existing_stat.traded_value = traded_val
                existing_stat.adv_20 = adv_20
                existing_stat.market_cap = market_cap
                existing_stat.shares_used = shares_used
                existing_stat.shares_as_of = shares_as_of
                existing_stat.flags = flags
                existing_stat.computed_at = now
                inserted_or_updated += 1
        else:
            stat_row = SecurityMarketStat(
                security_id=security_id,
                trade_date=price.trade_date,
                traded_value=traded_val,
                adv_20=adv_20,
                market_cap=market_cap,
                shares_used=shares_used,
                shares_as_of=shares_as_of,
                flags=flags,
                computed_at=now,
            )
            session.add(stat_row)
            existing_dates.add(price.trade_date)
            inserted_or_updated += 1

    session.flush()
    return inserted_or_updated


def derive_all_market_stats(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    cutoff: datetime | None = None,
) -> tuple[int, int]:
    """Derive market stats across all securities in the master."""
    securities = session.scalars(select(Security.id).where(Security.is_active.is_(True))).all()
    total_records = 0
    completed_securities = 0

    for sec_id in securities:
        count = derive_security_market_stats(
            session=session,
            security_id=sec_id,
            start_date=start_date,
            end_date=end_date,
            cutoff=cutoff,
        )
        total_records += count
        completed_securities += 1

    return completed_securities, total_records
