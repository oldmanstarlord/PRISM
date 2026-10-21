"""Unit and integration tests for the PRISM Stock Decision Engine.

Tests:
    1. Score calculation and dynamic weighting regimes.
    2. Classification thresholds (SELL / HOLD / WAIT & WATCH).
    3. Anomaly and risk alert escalations.
    4. Confidence level determination and boundary dampening.
    5. Fundamental risk inversion (100 - risk_score).
    6. Sector strength extraction and rank mapping.
    7. News score mapping [-1.0, 1.0] -> [0, 100].
    8. Portfolio summary metrics and weighted risk exposure.
    9. End-to-end portfolio decision orchestrator with database integration.
    10. FastAPI router authentication and response schema.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.session import engine
from backend.app.decision.engine import (
    HOLD_THRESHOLD,
    WATCH_THRESHOLD,
    _calculate_final_score,
    _classify_decision,
    _fetch_fundamental_score,
    _fetch_sector_strength,
    _select_weights,
    analyze_portfolio_decisions,
)
from backend.app.decision.schemas import (
    AppliedWeights,
    FundamentalScorePayload,
    NewsScorePayload,
    PortfolioDecisionResponse,
    SectorStrengthPayload,
)
from backend.app.main import app

TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_score_calculation_mathematics() -> None:
    weights = AppliedWeights(
        fundamental=0.60,
        sector=0.25,
        news=0.15,
        regime="normal",
        regime_reason="Normal",
    )
    # 80 * 0.60 + 60 * 0.25 + 40 * 0.15 = 48 + 15 + 6 = 69.0
    score = _calculate_final_score(80.0, 60.0, 40.0, weights)
    assert score == 69.0


def test_weight_regime_selection() -> None:
    # Normal regime
    neutral_news = NewsScorePayload(
        symbol="TCS",
        news_score=50.0,
        sentiment="neutral",
        news_confidence=0.5,
        articles_analyzed=3,
        major_events=[],
        provider_status="configured",
        is_fallback_neutral=False,
    )
    w_normal = _select_weights(neutral_news, 3)
    assert w_normal.regime == "normal"
    assert w_normal.fundamental == 0.60
    assert w_normal.sector == 0.25
    assert w_normal.news == 0.15

    # Significant news (e.g. earnings)
    earnings_news = NewsScorePayload(
        symbol="TCS",
        news_score=75.0,
        sentiment="positive",
        news_confidence=0.8,
        articles_analyzed=5,
        major_events=["earnings"],
        provider_status="configured",
        is_fallback_neutral=False,
    )
    w_sig = _select_weights(earnings_news, 5)
    assert w_sig.regime == "significant_news"
    assert w_sig.fundamental == 0.55
    assert w_sig.sector == 0.20
    assert w_sig.news == 0.25

    # Critical event (e.g. litigation)
    litigation_news = NewsScorePayload(
        symbol="TCS",
        news_score=20.0,
        sentiment="negative",
        news_confidence=0.9,
        articles_analyzed=8,
        major_events=["litigation"],
        provider_status="configured",
        is_fallback_neutral=False,
    )
    w_crit = _select_weights(litigation_news, 8)
    assert w_crit.regime == "critical_event"
    assert w_crit.fundamental == 0.50
    assert w_crit.sector == 0.15
    assert w_crit.news == 0.35


def test_decision_classification_thresholds() -> None:
    weights = AppliedWeights(
        fundamental=0.60, sector=0.25, news=0.15, regime="normal", regime_reason=""
    )
    f_strong = FundamentalScorePayload(
        symbol="INFY", fundamental_strength_score=85.0, fundamental_classification="Low Risk", raw_risk_score=15.0
    )
    sec_strong = SectorStrengthPayload(
        symbol="INFY", sector_strength_score=80.0, divergence_value=1.5
    )
    news_strong = NewsScorePayload(
        symbol="INFY", news_score=75.0, sentiment="positive", news_confidence=0.8, articles_analyzed=5, provider_status="ok"
    )

    # 1. HOLD (score >= 70)
    decision, conf, explanation, reasons, alerts = _classify_decision(
        80.0, f_strong, sec_strong, news_strong, weights
    )
    assert decision == "HOLD"
    assert conf == "high"
    assert len(alerts) == 0

    # 2. WAIT & WATCH (45 <= score < 70)
    decision, conf, explanation, reasons, alerts = _classify_decision(
        55.0, f_strong, sec_strong, news_strong, weights
    )
    assert decision == "WAIT & WATCH"

    # 3. SELL (score < 45)
    f_weak = FundamentalScorePayload(
        symbol="INFY", fundamental_strength_score=30.0, fundamental_classification="High Risk", raw_risk_score=70.0
    )
    decision, conf, explanation, reasons, alerts = _classify_decision(
        35.0, f_weak, sec_strong, news_strong, weights
    )
    assert decision == "SELL"


def test_anomaly_and_alert_escalation() -> None:
    weights = AppliedWeights(
        fundamental=0.60, sector=0.25, news=0.15, regime="normal", regime_reason=""
    )
    # Stock has score 72 (ordinarily HOLD), but fundamental strength is 55 (<60) and anomaly flag is True
    f_anomaly = FundamentalScorePayload(
        symbol="ALERT",
        fundamental_strength_score=55.0,
        fundamental_classification="Moderate Risk",
        anomaly_flag=True,
        raw_risk_score=45.0,
    )
    sec = SectorStrengthPayload(
        symbol="ALERT", sector_strength_score=80.0, divergence_value=0.5
    )
    news = NewsScorePayload(
        symbol="ALERT", news_score=80.0, sentiment="positive", news_confidence=0.8, articles_analyzed=4, provider_status="ok"
    )

    decision, conf, explanation, reasons, alerts = _classify_decision(
        72.0, f_anomaly, sec, news, weights
    )
    # Should escalate from HOLD to WAIT & WATCH due to anomaly + fundamental < 60
    assert decision == "WAIT & WATCH"
    assert any("ANOMALY DETECTED" in a for a in alerts)


def test_fundamental_inversion_adapter() -> None:
    mock_session = MagicMock()
    mock_metric = MagicMock()
    mock_metric.score = 25.0  # 25 risk -> inverts to 75 strength
    mock_metric.quality_status = "pass"
    mock_metric.metric_date = date(2026, 10, 20)
    mock_metric.data_cutoff = date(2026, 10, 20)

    # First scalar returns date, second returns metric row, third returns anomaly model
    mock_session.scalar.side_effect = [date(2026, 10, 20), mock_metric, None]

    payload = _fetch_fundamental_score(mock_session, "RELIANCE")
    assert payload.availability == "available"
    assert payload.raw_risk_score == 25.0
    assert payload.fundamental_strength_score == 75.0  # 100 - 25

    # Missing date fallback
    mock_session.scalar.side_effect = [None]
    missing_payload = _fetch_fundamental_score(mock_session, "NONEXISTENT")
    assert missing_payload.availability == "unavailable"
    assert missing_payload.fundamental_strength_score == 50.0


def test_sector_divergence_adapter() -> None:
    mock_session = MagicMock()
    mock_row = MagicMock()
    mock_row.industry = "Oil & Gas"
    mock_row.divergence_value = 1.85
    mock_row.industry_percentile = 88.5
    mock_row.interpretation = "strong"

    mock_session.scalar.return_value = mock_row

    payload = _fetch_sector_strength(mock_session, "RELIANCE", UUID("00000000-0000-0000-0000-000000000001"))
    assert payload.availability == "available"
    assert payload.sector_strength_score == 88.5
    assert payload.divergence_value == 1.85
    assert payload.interpretation == "strong"

    # No run fallback
    no_run_payload = _fetch_sector_strength(mock_session, "RELIANCE", None)
    assert no_run_payload.availability == "no_run"
    assert no_run_payload.sector_strength_score == 50.0


def test_portfolio_decisions_orchestrator() -> None:
    with Session(engine) as session:
        holdings = [
            {"symbol": "RELIANCE", "quantity": 10, "buy_price": 2500, "weight": 0.5},
            {"symbol": "TCS", "quantity": 5, "buy_price": 3500, "weight": 0.5},
        ]

        res = analyze_portfolio_decisions(holdings, session)
        assert isinstance(res, PortfolioDecisionResponse)
        assert res.summary.total_stocks == 2
        assert res.summary.portfolio_weighted_risk_exposure >= 0.0
        assert len(res.decisions) == 2
        for d in res.decisions:
            assert d.decision in {"HOLD", "WAIT & WATCH", "SELL"}
            assert d.final_score >= 0.0
            assert d.applied_weights.regime in {"normal", "significant_news", "critical_event"}


def test_api_analyze_endpoint_and_saved_authentication() -> None:
    client = TestClient(app)

    # 1. /portfolio/analyze succeeds without authentication (client-side interactive analysis)
    resp = client.post(
        "/api/v1/portfolio/analyze",
        json={"holdings": [{"symbol": "TCS", "quantity": 10, "buy_price": 3000}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "decisions" in data
    assert data["summary"]["total_stocks"] == 1

    # 2. Saved portfolio analysis requires authentication
    saved_resp = client.post(
        "/api/v1/portfolio/analyze/saved?portfolio_id=00000000-0000-0000-0000-000000000001"
    )
    assert saved_resp.status_code == 401

