"""Integration tests for portfolio service: idempotency, no-look-ahead, and artifacts."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import numpy as np
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    AnalyticsArtifact,
    BenchmarkDefinition,
    BenchmarkSeries,
    PortfolioRiskRun,
    PriceDailyAdjusted,
    Security,
    SecurityAlias,
)
from backend.app.portfolio.schemas import (
    HoldingInput,
    PortfolioCreate,
    RiskRunRequest,
)
from backend.app.portfolio.service import (
    create_portfolio,
    get_latest_risk_run,
    import_portfolio_csv,
    run_portfolio_risk,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed test securities
        sec1 = Security(
            id=uuid4(),
            isin="INE009A01021",
            company_name="Infosys Ltd",
            sector="Technology",
            industry="IT Services",
        )
        sec2 = Security(
            id=uuid4(),
            isin="INE467B01029",
            company_name="Tata Consultancy Services Ltd",
            sector="Technology",
            industry="IT Services",
        )
        session.add_all([sec1, sec2])
        session.flush()

        alias1 = SecurityAlias(
            security_id=sec1.id,
            symbol="INFY",
            exchange="NSE",
            valid_from=date(2020, 1, 1),
            source="NSE",
            ingested_at=date(2020, 1, 1),
        )
        alias2 = SecurityAlias(
            security_id=sec2.id,
            symbol="TCS",
            exchange="NSE",
            valid_from=date(2020, 1, 1),
            source="NSE",
            ingested_at=date(2020, 1, 1),
        )
        session.add_all([alias1, alias2])

        # Seed benchmark
        bench_def = BenchmarkDefinition(
            benchmark_id="NIFTY 200",
            name="Nifty 200",
            source="NSE",
        )
        session.add(bench_def)

        # Seed prices: 30 trading days up to 2026-10-01, plus a future day 2026-10-10
        start_date = date(2026, 8, 1)
        base_p1 = 1500.0
        base_p2 = 3500.0
        base_m = 12000.0
        np.random.seed(123)

        for i in range(35):
            t_date = start_date + timedelta(days=i)
            # Daily returns
            ret1 = float(np.random.normal(0.0005, 0.015))
            ret2 = float(np.random.normal(0.0003, 0.012))
            ret_m = float(np.random.normal(0.0004, 0.010))

            base_p1 *= float(np.exp(ret1))
            base_p2 *= float(np.exp(ret2))
            base_m *= float(np.exp(ret_m))

            session.add(
                PriceDailyAdjusted(
                    id=uuid4(),
                    security_id=sec1.id,
                    trade_date=t_date,
                    adjusted_close=Decimal(str(round(base_p1, 4))),
                    method_version="official_v1",
                    computed_at=date(2026, 10, 1),
                )
            )
            session.add(
                PriceDailyAdjusted(
                    id=uuid4(),
                    security_id=sec2.id,
                    trade_date=t_date,
                    adjusted_close=Decimal(str(round(base_p2, 4))),
                    method_version="official_v1",
                    computed_at=date(2026, 10, 1),
                )
            )
            session.add(
                BenchmarkSeries(
                    id=uuid4(),
                    benchmark_id="NIFTY 200",
                    trade_date=t_date,
                    close=Decimal(str(round(base_m, 4))),
                    source="NSE",
                    method_version="official_daily_v1",
                    ingested_at=date(2026, 10, 1),
                )
            )

        # Future price on 2026-10-10 (must NEVER be included when as_of is 2026-10-01)
        future_date = date(2026, 10, 10)
        session.add(
            PriceDailyAdjusted(
                id=uuid4(),
                security_id=sec1.id,
                trade_date=future_date,
                adjusted_close=Decimal("99999.0"),  # Extreme price to catch any lookahead
                method_version="official_v1",
                computed_at=date(2026, 10, 10),
            )
        )

        session.commit()
        yield session


def test_no_lookahead_and_portfolio_risk_execution(db_session: Session) -> None:
    """Verify that calculations on as_of=2026-10-01 strictly ignore prices after that date."""
    as_of = date(2026, 10, 1)

    port = create_portfolio(
        session=db_session,
        payload=PortfolioCreate(
            name="Tech Growth",
            description="High quality IT firms",
            as_of=as_of,
            holdings=[
                HoldingInput(symbol="INFY", weight=0.6),
                HoldingInput(symbol="TCS", weight=0.4),
            ],
        ),
    )

    req = RiskRunRequest(
        as_of=as_of,
        config_version="1.0.0",
        shrinkage_override=0.0,
    )

    result = run_portfolio_risk(db_session, port.id, req)

    # Volatility must be reasonable (around 10-30%), not distorted by the future 99999.0 price
    assert 0.05 < result.portfolio_volatility < 0.50
    assert result.as_of == as_of
    assert result.status == "completed"
    assert len(result.contributions) == 2

    # Verify Parquet artifact was recorded
    artifact = db_session.scalar(
        select(AnalyticsArtifact).where(AnalyticsArtifact.run_id == result.id)
    )
    assert artifact is not None
    assert artifact.artifact_type == "covariance_matrix_parquet"
    assert len(artifact.content_hash) == 64  # SHA-256


def test_idempotent_re_run_creates_no_new_rows(db_session: Session) -> None:
    """Verify D6 IDEMPOTENT RUNS: repeating run reuses completed run without new DB rows."""
    as_of = date(2026, 10, 1)

    port = create_portfolio(
        session=db_session,
        payload=PortfolioCreate(
            name="Idempotency Test",
            as_of=as_of,
            holdings=[
                HoldingInput(symbol="INFY", weight=0.5),
                HoldingInput(symbol="TCS", weight=0.5),
            ],
        ),
    )

    req = RiskRunRequest(as_of=as_of)

    # First run
    run1 = run_portfolio_risk(db_session, port.id, req)
    count_after_first = db_session.scalar(select(func.count(PortfolioRiskRun.id))) or 0

    # Repeat run with identical inputs
    run2 = run_portfolio_risk(db_session, port.id, req)
    count_after_second = db_session.scalar(select(func.count(PortfolioRiskRun.id))) or 0

    # Must be exact same run ID and no new rows created
    assert run1.id == run2.id
    assert run1.input_fingerprint == run2.input_fingerprint
    assert count_after_first == count_after_second

    # Test GET /portfolios/{id}/risk/latest
    latest = get_latest_risk_run(db_session, port.id)
    assert latest.id == run1.id


def test_csv_import_workflow(db_session: Session) -> None:
    """Verify CSV import with valid and invalid rows."""
    csv_valid = """symbol,weight
INFY,0.70
TCS,0.30
"""
    res = import_portfolio_csv(
        session=db_session,
        name="Imported Tech",
        csv_content=csv_valid,
        as_of=date(2026, 10, 1),
    )
    assert res.portfolio is not None
    assert not res.errors
    assert len(res.portfolio.holdings) == 2

    # CSV with unknown symbol
    csv_invalid = """symbol,weight
INFY,0.50
UNKNOWN_CO,0.50
"""
    res_err = import_portfolio_csv(
        session=db_session,
        name="Bad Import",
        csv_content=csv_invalid,
        as_of=date(2026, 10, 1),
    )
    assert res_err.portfolio is None
    assert len(res_err.errors) == 1
    assert res_err.errors[0].symbol == "UNKNOWN_CO"
    assert "Unknown security" in res_err.errors[0].error
