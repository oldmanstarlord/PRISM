"""Tests for News Impact and Explanation API routes (Step E4)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.news_impact.schemas import (
    AffectedStockOut,
    NewsImpactPathOut,
    NewsInsightOut,
    NewsInsightsResponse,
    PortfolioHoldingImpactOut,
    PortfolioNewsOverlayOut,
)


def test_news_insights_endpoint_pure_logic() -> None:
    client = TestClient(app)
    news_id = uuid4()
    mock_response = NewsInsightsResponse(
        items=[
            NewsInsightOut(
                news_id=news_id,
                headline="RBI policy rate update",
                source="RBI",
                published_at=datetime.now(UTC),
                url="https://rbi.org.in/press",
                severity=7.5,
                affected_industries=["Banks"],
                matched_rules=["POL_RBI_RATE_HIKE_V1"],
                unreviewed=False,
                affected_stocks=[
                  AffectedStockOut(
                      symbol="HDFCBANK",
                      security_id=uuid4(),
                      industry="Banks",
                      direction="headwind",
                      exposure_score=0.62,
                      exposure_band="medium",
                      confidence=0.85,
                      paths=[
                          NewsImpactPathOut(
                              path_type="rule",
                              direction="headwind",
                              severity=7.5,
                              exposure_score=0.62,
                              exposure_band="medium",
                              confidence=0.85,
                              evidence=[{"source_table": "policy_rule", "source_ref": "rule-1"}],
                          )
                      ],
                  )
                ],
            )
        ],
        source_statuses=[],
        limitations=["Possible effect, not a prediction or advice."],
    )

    from backend.app.api.v1 import router as api_router

    def mock_list(*args, **kwargs):
        return mock_response

    original_service_call = api_router.list_news_insights
    api_router.list_news_insights = mock_list
    try:
        response = client.get("/api/v1/news/insights")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["headline"] == "RBI policy rate update"
        assert data["items"][0]["severity"] == 7.5
        assert len(data["items"][0]["affected_stocks"]) == 1
        assert data["items"][0]["affected_stocks"][0]["symbol"] == "HDFCBANK"
    finally:
        api_router.list_news_insights = original_service_call


def test_explain_news_endpoint_not_found() -> None:
    client = TestClient(app)
    unknown_id = uuid4()
    from backend.app.api.v1 import router as api_router

    def raise_lookup(session, news_id):
        raise LookupError("News impact not found")

    original_fn = api_router.get_or_create_news_explanation
    api_router.get_or_create_news_explanation = raise_lookup
    try:
        response = client.get(f"/api/v1/explain/news/{unknown_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        api_router.get_or_create_news_explanation = original_fn


def test_explain_portfolio_news_overlay_endpoint() -> None:
    client = TestClient(app)
    portfolio_id = uuid4()
    news_id = uuid4()

    mock_overlay = PortfolioNewsOverlayOut(
        portfolio_id=portfolio_id,
        news_id=news_id,
        as_of=datetime.now(UTC),
        affected_industry_weight=0.25,
        holdings=[
            PortfolioHoldingImpactOut(
                symbol="HDFCBANK",
                industry="Banks",
                weight=0.25,
                risk_contribution=0.30,
                exposure_score=0.62,
                exposure_band="medium",
                cluster_id="cluster-1",
            )
        ],
        cluster_overlap={},
        inputs=["fingerprint"],
        thresholds={"spillover_min_r_squared": 0.25},
        confidence=0.85,
        data_age_days=1,
        limitations=["Descriptive scenario, not price prediction."],
        disclaimer="Not investment advice.",
    )

    from backend.app.api.v1 import router as api_router

    original_fn = api_router.get_portfolio_news_overlay
    api_router.get_portfolio_news_overlay = lambda session, p_id, n_id: mock_overlay
    try:
        response = client.get(f"/api/v1/explain/portfolio/{portfolio_id}/news/{news_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["portfolio_id"] == str(portfolio_id)
        assert data["news_id"] == str(news_id)
        assert data["affected_industry_weight"] == 0.25
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "HDFCBANK"
        assert data["predicted_changes"] == []
    finally:
        api_router.get_portfolio_news_overlay = original_fn
