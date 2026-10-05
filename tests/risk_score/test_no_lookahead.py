"""Tests verifying point-in-time isolation (D4) and idempotent re-runs (D6)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Base,
    ModelConfig,
    PriceDailyAdjusted,
    ScoreRun,
    Security,
    SecurityAlias,
)
from backend.app.risk_score.components.base import RiskContext
from backend.app.risk_score.components.helpers import get_adjusted_prices_map
from backend.app.risk_score.service import _canonical_hash, run_stock_score_calculation


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_no_lookahead_filtering(memory_db: Session) -> None:
    """Ensure data with trade_date > as_of or computed_at > data_cutoff is strictly omitted (D4)."""
    sec_id = uuid4()
    sec = Security(
        id=sec_id,
        isin="INE467B01029",
        company_name="Tata Consultancy Services Ltd.",
        industry="Information Technology",
        is_active=True,
    )
    alias = SecurityAlias(
        id=uuid4(),
        security_id=sec_id,
        symbol="TCS",
        exchange="NSE",
        valid_from=date(2020, 1, 1),
        source="NSE",
        ingested_at=datetime.now(UTC),
    )
    memory_db.add_all([sec, alias])

    as_of = date(2026, 1, 10)
    cutoff = datetime(2026, 1, 10, 18, 0, 0, tzinfo=UTC)

    # Valid in-window observation
    p1 = PriceDailyAdjusted(
        id=uuid4(),
        security_id=sec_id,
        trade_date=date(2026, 1, 9),
        adjusted_close=Decimal("3800.0"),
        method_version="official_daily_v1",
        computed_at=datetime(2026, 1, 9, 18, 0, 0, tzinfo=UTC),
    )
    # Valid on-date observation
    p2 = PriceDailyAdjusted(
        id=uuid4(),
        security_id=sec_id,
        trade_date=date(2026, 1, 10),
        adjusted_close=Decimal("3820.0"),
        method_version="official_daily_v1",
        computed_at=datetime(2026, 1, 10, 17, 30, 0, tzinfo=UTC),
    )
    # FUTURE observation (trade_date > as_of)
    p3_future = PriceDailyAdjusted(
        id=uuid4(),
        security_id=sec_id,
        trade_date=date(2026, 1, 11),
        adjusted_close=Decimal("4500.0"),
        method_version="official_daily_v1",
        computed_at=datetime(2026, 1, 11, 18, 0, 0, tzinfo=UTC),
    )
    # LATE computed observation (computed_at > cutoff)
    p4_late = PriceDailyAdjusted(
        id=uuid4(),
        security_id=sec_id,
        trade_date=date(2026, 1, 10),
        adjusted_close=Decimal("3900.0"),
        method_version="official_daily_v2",
        computed_at=datetime(2026, 1, 10, 20, 0, 0, tzinfo=UTC),
    )
    memory_db.add_all([p1, p2, p3_future, p4_late])
    memory_db.commit()

    context = RiskContext(
        session=memory_db,
        as_of=as_of,
        data_cutoff=cutoff,
        config={},
    )
    prices_map = get_adjusted_prices_map(context, [(sec_id, "TCS", "IT")], lookback_days=30)
    series = prices_map[sec_id]

    assert len(series) == 2
    assert date(2026, 1, 11) not in series.index
    assert float(series.loc[date(2026, 1, 10)]) == 3820.0


def test_idempotent_run_execution(memory_db: Session) -> None:
    """Ensure identical inputs and configuration reuse the completed run (D6)."""
    sec_id = uuid4()
    sec = Security(
        id=sec_id,
        isin="INE009A01021",
        company_name="Infosys Ltd.",
        industry="Information Technology",
        is_active=True,
    )
    alias = SecurityAlias(
        id=uuid4(),
        security_id=sec_id,
        symbol="INFY",
        exchange="NSE",
        valid_from=date(2020, 1, 1),
        source="NSE",
        ingested_at=datetime.now(UTC),
    )
    memory_db.add_all([sec, alias])

    # Seed model config
    cfg_payload = {"min_coverage_ratio": 0.70}
    cfg = ModelConfig(
        id=uuid4(),
        config_key="risk_engine_parameters",
        version="1.0.0",
        status="approved",
        configuration=cfg_payload,
        configuration_hash=_canonical_hash(cfg_payload),
    )
    memory_db.add(cfg)
    memory_db.commit()

    as_of = date(2026, 1, 10)
    cutoff = datetime(2026, 1, 10, 23, 59, 59, tzinfo=UTC)

    # First run: should be created
    res1 = run_stock_score_calculation(
        session=memory_db,
        as_of=as_of,
        data_cutoff=cutoff,
        config_version="1.0.0",
        force=False,
    )
    assert res1.is_new is True

    # Second run: should be reused
    res2 = run_stock_score_calculation(
        session=memory_db,
        as_of=as_of,
        data_cutoff=cutoff,
        config_version="1.0.0",
        force=False,
    )
    assert res2.is_new is False
    assert res2.run_id == res1.run_id

    # Verify no duplicate score_run rows were created
    runs = memory_db.scalars(select(ScoreRun)).all()
    assert len(runs) == 1
