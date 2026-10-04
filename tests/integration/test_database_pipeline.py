import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import exp, sin
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
import pytest
from sqlalchemy import func, select, text

from backend.app.correlation_mst.service import persist_mst
from backend.app.db.models import (
    PriceDailyAdjusted,
    Security,
    SecurityAlias,
    Universe,
    UniverseMembership,
)
from backend.app.db.session import SessionLocal
from backend.app.sector_divergence.service import latest_market_snapshot, persist_calculation

pytestmark = pytest.mark.integration


def _seed_synthetic_snapshot() -> None:
    with SessionLocal() as session:
        if session.scalar(select(func.count()).select_from(Universe)):
            return
        universe = Universe(name="NIFTY 200", description="CI synthetic universe")
        session.add(universe)
        session.flush()
        start = date(2026, 1, 1)
        cutoff = datetime(2026, 10, 2, tzinfo=UTC)
        dates = [value.date() for value in pd.bdate_range(start, periods=121)]
        for symbol_index in range(5):
            security_id = UUID(int=symbol_index + 1)
            security = Security(
                id=security_id,
                isin=f"INE{symbol_index:09d}",
                company_name=f"Synthetic {symbol_index}",
                industry="Synthetic Industry",
            )
            session.add(security)
            session.add(
                SecurityAlias(
                    security_id=security_id,
                    symbol=f"TEST{symbol_index}",
                    exchange="NSE",
                    valid_from=start,
                    source="ci-synthetic",
                    ingested_at=cutoff,
                )
            )
            session.add(
                UniverseMembership(
                    universe_id=universe.id,
                    security_id=security_id,
                    valid_from=start,
                    source="ci-synthetic",
                    ingested_at=cutoff,
                )
            )
            price = 100.0
            for position, trade_date in enumerate(dates):
                if position:
                    daily_return = (
                        0.0004
                        + 0.002 * sin(position / (5 + symbol_index))
                        + symbol_index * 0.00003
                    )
                    price *= exp(daily_return)
                session.add(
                    PriceDailyAdjusted(
                        security_id=security_id,
                        trade_date=trade_date,
                        adjusted_close=Decimal(str(price)),
                        method_version="yfinance-adjclose-v1-r1",
                        computed_at=cutoff,
                    )
                )
        session.commit()


@pytest.mark.skipif(
    os.getenv("PRISM_RUN_DB_INTEGRATION") != "1",
    reason="Set PRISM_RUN_DB_INTEGRATION=1 only for an approved PostgreSQL test database",
)
def test_migrations_and_quantitative_runs_are_idempotent() -> None:
    _seed_synthetic_snapshot()
    with SessionLocal() as session:
        revision = session.scalar(text("select version_num from alembic_version"))
        assert revision == "9c41ad7b218e"
        market_date, cutoff = latest_market_snapshot(session)
        first_l1 = persist_calculation(
            session,
            signal_date=market_date,
            lookback_start=market_date - timedelta(days=180),
            data_cutoff=cutoff,
        )
        second_l1 = persist_calculation(
            session,
            signal_date=market_date,
            lookback_start=market_date - timedelta(days=180),
            data_cutoff=cutoff,
        )
        first_l2 = persist_mst(
            session,
            window_end=market_date,
            lookback_start=market_date - timedelta(days=220),
            data_cutoff=cutoff,
        )
        second_l2 = persist_mst(
            session,
            window_end=market_date,
            lookback_start=market_date - timedelta(days=220),
            data_cutoff=cutoff,
        )
    assert first_l1.run_id == second_l1.run_id
    assert second_l1.created is False
    assert first_l2.run_id == second_l2.run_id
    assert second_l2.created is False
