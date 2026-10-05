"""Tests for Step 8 governance components and component registry integration (D2)."""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.risk_score.components.base import RiskContext
from backend.app.risk_score.components.governance import (
    GovInstitutionalFlowComponent,
    GovPromoterHoldingChangeComponent,
    GovPromoterPledgeComponent,
)
from backend.app.risk_score.registry import registry


def test_governance_components_registered() -> None:
    """All 4 Step 8 governance components are registered and active (D2)."""
    step8_keys = [
        "gov_promoter_pledge",
        "gov_promoter_holding_change",
        "gov_institutional_flow",
        "gov_insider_activity",
    ]

    for key in step8_keys:
        defn = registry.get_definition(key)
        assert defn is not None, f"Component {key} not registered"
        assert defn.dimension == "governance"
        assert defn.direction == "higher_is_riskier"
        assert defn.active is True
        assert defn.introduced_in_step == "Step 8"


def test_governance_components_missing_data_handling() -> None:
    """Components handle missing data gracefully (status='missing', raw_value=None)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        as_of = date(2026, 1, 15)
        cutoff = datetime(2026, 1, 15, 23, 59, tzinfo=UTC)
        context = RiskContext(
            session=session,
            as_of=as_of,
            data_cutoff=cutoff,
            config={},
            cache={},
        )

        sec_id = uuid4()
        universe = [(sec_id, "TESTCO", "Information Technology")]

        # 1. Pledge Component
        pledge_comp = GovPromoterPledgeComponent()
        pledge_out = pledge_comp.compute(as_of, universe, context)
        assert len(pledge_out) == 1
        assert pledge_out[0].status == "missing"
        assert pledge_out[0].raw_value is None

        # 2. Promoter Holding Change Component
        holding_comp = GovPromoterHoldingChangeComponent()
        holding_out = holding_comp.compute(as_of, universe, context)
        assert len(holding_out) == 1
        assert holding_out[0].status == "missing"
        assert holding_out[0].raw_value is None

        # 3. Institutional Flow Component
        inst_comp = GovInstitutionalFlowComponent()
        inst_out = inst_comp.compute(as_of, universe, context)
        assert len(inst_out) == 1
        assert inst_out[0].status == "missing"
        assert inst_out[0].raw_value is None


def test_governance_components_with_cached_data_and_determinism() -> None:
    """With populated context cache, components calculate deterministically (D6)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        as_of = date(2026, 1, 15)
        cutoff = datetime(2026, 1, 15, 23, 59, tzinfo=UTC)
        sec_id = uuid4()

        cached_patterns = [
            {
                "quarter_end": date(2025, 12, 31),
                "promoter_pct": 55.0,
                "promoter_pledged_pct_of_promoter": 20.0,
                "fii_pct": 22.0,
                "dii_pct": 14.0,
                "public_pct": 9.0,
                "published_at": datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
                "version": 1,
            },
            {
                "quarter_end": date(2025, 9, 30),
                "promoter_pct": 55.0,
                "promoter_pledged_pct_of_promoter": 15.0,
                "fii_pct": 20.0,
                "dii_pct": 14.0,
                "public_pct": 11.0,
                "published_at": datetime(2025, 10, 15, 10, 0, tzinfo=UTC),
                "version": 1,
            },
            {
                "quarter_end": date(2025, 6, 30),
                "promoter_pct": 57.0,
                "promoter_pledged_pct_of_promoter": 12.0,
                "fii_pct": 19.0,
                "dii_pct": 13.0,
                "public_pct": 11.0,
                "published_at": datetime(2025, 7, 15, 10, 0, tzinfo=UTC),
                "version": 1,
            },
        ]

        context = RiskContext(
            session=session,
            as_of=as_of,
            data_cutoff=cutoff,
            config={},
            cache={f"shareholding_{sec_id}": cached_patterns},
        )

        universe = [(sec_id, "TESTCO", "Information Technology")]

        # Pledge component calculation:
        # Latest pledge level = 20.0, 2Q change = 20.0 - 15.0 = +5.0
        # Composite raw = 20.0 + 5.0 * 0.5 = 22.5
        comp = GovPromoterPledgeComponent()
        out1 = comp.compute(as_of, universe, context)
        out2 = comp.compute(as_of, universe, context)

        assert len(out1) == 1
        assert out1[0].status == "ok"
        assert out1[0].raw_value == 22.5
        # Determinism
        assert out1[0].raw_value == out2[0].raw_value
        assert out1[0].status == out2[0].status
