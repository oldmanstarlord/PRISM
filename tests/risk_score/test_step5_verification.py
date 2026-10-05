"""Tests verifying Step 5 requirements: determinism, missing benchmark handling,
and MST diagnostics idempotency.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Base,
    MstCluster,
    MstEdge,
    MstNode,
    MstNodeMetric,
    MstRun,
    Security,
    Universe,
)
from backend.app.mst_diagnostics.service import compute_and_persist_diagnostics
from backend.app.risk_score.components.base import ComponentValue, RiskContext
from backend.app.risk_score.components.beta_to_benchmark import BetaToBenchmarkComponent
from backend.app.risk_score.registry import RegisteredComponentDefinition
from backend.app.risk_score.scorer import RiskScorer


@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Test 1: Determinism of component values and scores
# ---------------------------------------------------------------------------
def test_risk_scorer_determinism() -> None:
    u1, u2, u3, u4, u5 = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    universe = [
        (u1, "STK1", "IT"),
        (u2, "STK2", "IT"),
        (u3, "STK3", "Fin"),
        (u4, "STK4", "Fin"),
        (u5, "STK5", "Energy"),
    ]
    definitions = {
        "comp_a": RegisteredComponentDefinition(
            id=None,
            component_id="comp_a",
            dimension="market",
            name="Metric A",
            description="",
            direction="higher_is_riskier",
            scope="universe",
            min_group_size=5,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
        "comp_b": RegisteredComponentDefinition(
            id=None,
            component_id="comp_b",
            dimension="correlation_structure",
            name="Metric B",
            description="",
            direction="lower_is_riskier",
            scope="universe",
            min_group_size=5,
            weight=1.0,
            active=True,
            introduced_in_step="Step 5",
        ),
    }

    comp_values = {
        "comp_a": [
            ComponentValue(u1, "STK1", "comp_a", 10.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u2, "STK2", "comp_a", 20.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u3, "STK3", "comp_a", 30.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u4, "STK4", "comp_a", 40.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u5, "STK5", "comp_a", 50.0, "ok", date(2026, 1, 1), 0),
        ],
        "comp_b": [
            ComponentValue(u1, "STK1", "comp_b", 5.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u2, "STK2", "comp_b", 4.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u3, "STK3", "comp_b", 3.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u4, "STK4", "comp_b", 2.0, "ok", date(2026, 1, 1), 0),
            ComponentValue(u5, "STK5", "comp_b", 1.0, "ok", date(2026, 1, 1), 0),
        ],
    }

    config = {
        "dimension_weights": {"market": 25.0, "correlation_structure": 20.0},
        "min_coverage_ratio": 0.20,
    }

    scorer1 = RiskScorer(config=config, definitions=definitions)
    res1 = scorer1.synthesize(universe=universe, component_values_by_key=comp_values)

    scorer2 = RiskScorer(config=config, definitions=definitions)
    res2 = scorer2.synthesize(universe=universe, component_values_by_key=comp_values)

    assert len(res1) == len(res2) == 5
    for s_id in [u1, u2, u3, u4, u5]:
        assert res1[s_id].overall_score == res2[s_id].overall_score
        assert res1[s_id].coverage == res2[s_id].coverage
        assert res1[s_id].status == res2[s_id].status


# ---------------------------------------------------------------------------
# Test 4: Missing benchmark returns status="missing" with reason="benchmark_unavailable"
# ---------------------------------------------------------------------------
def test_missing_benchmark_yields_missing_status_and_no_fallback(mem_db: Session) -> None:
    comp = BetaToBenchmarkComponent()
    as_of = date(2026, 1, 15)
    cutoff = datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC)

    u1, u2 = uuid4(), uuid4()
    universe = [(u1, "TCS", "IT"), (u2, "INFY", "IT")]

    # Empty context with no benchmark series in DB
    context = RiskContext(
        session=mem_db,
        as_of=as_of,
        data_cutoff=cutoff,
        config={"benchmark_id": "NIFTY_200"},
    )

    results = comp.compute(as_of=as_of, universe=universe, context=context)

    assert len(results) == 2
    for r in results:
        assert r.status == "missing"
        assert r.raw_value is None
        assert r.evidence_ref == {"reason": "benchmark_unavailable"}


# ---------------------------------------------------------------------------
# Test 5: MST diagnostics idempotency
# ---------------------------------------------------------------------------
def test_mst_diagnostics_calculation_is_idempotent(mem_db: Session) -> None:
    # 1. Universe and Securities
    u_id = uuid4()
    univ = Universe(id=u_id, name="NIFTY_200_TEST")
    mem_db.add(univ)

    s1, s2, s3 = uuid4(), uuid4(), uuid4()
    sec1 = Security(
        id=s1,
        isin="INE000000001",
        company_name="A Ltd",
        sector="Tech",
        industry="Software",
        is_active=True,
    )
    sec2 = Security(
        id=s2,
        isin="INE000000002",
        company_name="B Ltd",
        sector="Tech",
        industry="Software",
        is_active=True,
    )
    sec3 = Security(
        id=s3,
        isin="INE000000003",
        company_name="C Ltd",
        sector="Tech",
        industry="Software",
        is_active=True,
    )
    mem_db.add_all([sec1, sec2, sec3])
    mem_db.flush()

    # 2. Completed MstRun with 3 nodes and 2 edges
    run_id = uuid4()
    run = MstRun(
        id=run_id,
        universe_id=u_id,
        window_start=date(2025, 1, 1),
        window_end=date(2026, 1, 1),
        implementation_version="1.0.0",
        configuration={"variant": "raw"},
        input_fingerprint="fp1",
        status="completed",
        requested_symbol_count=3,
        included_symbol_count=3,
        edge_count=2,
        is_connected=True,
        is_acyclic=True,
        computed_at=datetime.now(UTC),
    )
    nodes = [
        MstNode(
            id=uuid4(),
            mst_run_id=run_id,
            security_id=s1,
            symbol="AAA",
            industry="Tech",
            observations_used=200,
            membership_source="test",
        ),
        MstNode(
            id=uuid4(),
            mst_run_id=run_id,
            security_id=s2,
            symbol="BBB",
            industry="Tech",
            observations_used=200,
            membership_source="test",
        ),
        MstNode(
            id=uuid4(),
            mst_run_id=run_id,
            security_id=s3,
            symbol="CCC",
            industry="Tech",
            observations_used=200,
            membership_source="test",
        ),
    ]
    edges = [
        MstEdge(
            id=uuid4(),
            mst_run_id=run_id,
            security_a_id=s1,
            security_b_id=s2,
            symbol_a="AAA",
            symbol_b="BBB",
            distance=Decimal("0.5"),
            correlation=Decimal("0.75"),
            edge_rank=1,
        ),
        MstEdge(
            id=uuid4(),
            mst_run_id=run_id,
            security_a_id=s2,
            security_b_id=s3,
            symbol_a="BBB",
            symbol_b="CCC",
            distance=Decimal("0.6"),
            correlation=Decimal("0.64"),
            edge_rank=2,
        ),
    ]
    mem_db.add(run)
    mem_db.add_all(nodes)
    mem_db.add_all(edges)
    mem_db.commit()

    # First run: diagnostics computed and persisted
    res1 = compute_and_persist_diagnostics(session=mem_db, run_id=run_id)
    assert res1.node_metrics_count == 3

    clusters_count_1 = len(
        mem_db.scalars(select(MstCluster).where(MstCluster.run_id == run_id)).all()
    )
    metrics_count_1 = len(
        mem_db.scalars(select(MstNodeMetric).where(MstNodeMetric.run_id == run_id)).all()
    )
    assert clusters_count_1 == 3
    assert metrics_count_1 == 3

    # Second run: must be completely idempotent, creating 0 new rows
    compute_and_persist_diagnostics(session=mem_db, run_id=run_id)
    clusters_count_2 = len(
        mem_db.scalars(select(MstCluster).where(MstCluster.run_id == run_id)).all()
    )
    metrics_count_2 = len(
        mem_db.scalars(select(MstNodeMetric).where(MstNodeMetric.run_id == run_id)).all()
    )

    assert clusters_count_2 == clusters_count_1
    assert metrics_count_2 == metrics_count_1
