"""Tests for ConfidenceEngine factors and hard caps (CONFIDENCE_SPEC.md)."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.risk_score.components.base import RiskContext
from backend.app.risk_score.confidence import ConfidenceEngine
from backend.app.risk_score.scorer import ScoredComponent, ScoredDimension, SecurityRiskScore


def test_confidence_caps_and_factors() -> None:
    sec_id = uuid4()
    as_of = date(2026, 1, 15)

    # Mock RiskContext
    session_mock = MagicMock()
    session_mock.scalars.return_value.all.return_value = []
    session_mock.scalars.return_value.first.return_value = None

    context = RiskContext(
        session=session_mock,
        as_of=as_of,
        data_cutoff=datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC),
        config={},
    )

    # 1. Test Low Coverage Cap (coverage < 0.70 => capped at 60.0)
    score_low_cov = SecurityRiskScore(
        security_id=sec_id,
        symbol="TEST",
        industry="Tech",
        overall_score=75.0,
        coverage=0.45,  # < 0.70
        status="insufficient",
        dimensions={
            "market": ScoredDimension(dimension="market", score=75.0, weight=25.0, status="ok"),
        },
        components=[
            ScoredComponent(
                component_id="ewma_volatility",
                dimension="market",
                name="EWMA Realised Volatility",
                raw_value=0.25,
                percentile=75.0,
                direction="higher_is_riskier",
                points=75.0,
                status="ok",
                data_as_of=as_of,
                data_age_days=1,
                weight=1.0,
                contribution=18.75,
                scope_used="universe",
            )
        ],
        top_reasons=[],
        limitations=["low_data_coverage_45.0%"],
    )

    engine = ConfidenceEngine({})
    results = engine.evaluate({sec_id: score_low_cov}, context)
    res = results[sec_id]

    assert res.final_confidence <= 60.0
    assert any("low_coverage_cap" in cap for cap in res.caps_applied)
    assert "data_coverage" in res.factors
    assert res.factors["data_coverage"].factor_value == 0.45


def test_confidence_stale_price_cap() -> None:
    sec_id = uuid4()
    as_of = date(2026, 1, 15)

    session_mock = MagicMock()
    session_mock.scalars.return_value.all.return_value = []
    session_mock.scalars.return_value.first.return_value = None

    context = RiskContext(
        session=session_mock,
        as_of=as_of,
        data_cutoff=datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC),
        config={},
    )

    # Stale market component (data_age_days = 7 > 5)
    score_stale = SecurityRiskScore(
        security_id=sec_id,
        symbol="STALE_CORP",
        industry="Auto",
        overall_score=50.0,
        coverage=1.0,  # Full coverage
        status="partial",
        dimensions={
            "market": ScoredDimension(dimension="market", score=50.0, weight=25.0, status="ok"),
        },
        components=[
            ScoredComponent(
                component_id="ewma_volatility",
                dimension="market",
                name="EWMA Realised Volatility",
                raw_value=0.30,
                percentile=50.0,
                direction="higher_is_riskier",
                points=50.0,
                status="stale",
                data_as_of=date(2026, 1, 8),
                data_age_days=7,
                weight=1.0,
                contribution=12.5,
                scope_used="universe",
            )
        ],
        top_reasons=[],
        limitations=["stale_data_ewma_volatility"],
    )

    engine = ConfidenceEngine({})
    results = engine.evaluate({sec_id: score_stale}, context)
    res = results[sec_id]

    # Stale price cap must cap confidence at 50.0
    assert res.final_confidence <= 50.0
    assert any("stale_price_cap" in cap for cap in res.caps_applied)
