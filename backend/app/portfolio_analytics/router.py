"""Bounded, non-persistent portfolio analytics and stock-level risk API."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import StockMetricDaily
from backend.app.db.session import get_session
from backend.app.market_data.metrics import METHODOLOGY_VERSION
from backend.app.portfolio_analytics.methodology_registry import get_methodology_manifest
from backend.app.portfolio_analytics.schemas import (
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
)
from backend.app.portfolio_analytics.service import analyze_portfolio
from backend.app.portfolio_analytics.stock_risk import (
    calculate_portfolio_comprehensive_risk,
)
from backend.app.portfolio_analytics.structural_monitoring import (
    CorrelatedHoldingGroup,
    StructuralMonitoringSnapshot,
    compute_historical_risk_series,
    evaluate_monitoring_indicators,
)

router = APIRouter(prefix="/portfolio-analysis", tags=["portfolio analysis"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]
logger = logging.getLogger(__name__)


class AnalyticsRequestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class HoldingRiskInput(AnalyticsRequestModel):
    symbol: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9&.-]+$")
    companyName: str | None = Field(default=None, max_length=255)
    sector: str | None = Field(default=None, max_length=160)
    quantity: float = Field(default=1.0, gt=0)
    buyPrice: float = Field(default=1.0, gt=0)
    buyDate: str | None = None
    exchange: str = Field(default="NSE", min_length=1, max_length=16)


class ComprehensiveRiskRequest(AnalyticsRequestModel):
    holdings: list[HoldingRiskInput] = Field(min_length=1, max_length=150)
    thresholds: dict[str, float] | None = None


@router.get("/methodology")
def get_methodology() -> dict[str, Any]:
    """Return the authoritative PRISM quantitative risk methodology registry."""
    return get_methodology_manifest()


@router.post("/preview", response_model=PortfolioAnalysisResponse)
def preview_portfolio_analysis(
    payload: PortfolioAnalysisRequest,
    session: DatabaseSession,
) -> PortfolioAnalysisResponse:
    """Calculate real portfolio analytics without authentication or persistence."""
    try:
        return analyze_portfolio(session, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/comprehensive-risk")
def calculate_comprehensive_risk(
    payload: ComprehensiveRiskRequest,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Calculate multi-window stock-level risk, portfolio covariance, Euler risk share,
    and diversification.
    """
    try:
        holdings_dicts = [h.model_dump() for h in payload.holdings]
        stock_profiles, portfolio_profile = calculate_portfolio_comprehensive_risk(
            holdings_dicts, session
        )
        return {
            "data_date": session.scalar(
                select(func.max(StockMetricDaily.metric_date)).where(
                    StockMetricDaily.methodology_version == METHODOLOGY_VERSION
                )
            ),
            "stock_profiles": [p.to_dict() for p in stock_profiles],
            "portfolio_profile": portfolio_profile.to_dict(),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Comprehensive risk calculation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Risk calculation is temporarily unavailable",
        ) from exc


@router.post("/structural-monitoring")
def get_structural_monitoring(
    payload: ComprehensiveRiskRequest,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Generate the unified structural monitoring snapshot, analytical indicators,
    correlated holding groups, and historical risk series.
    """
    try:
        holdings_dicts = [h.model_dump() for h in payload.holdings]
        stock_profiles, portfolio_profile = calculate_portfolio_comprehensive_risk(
            holdings_dicts, session
        )

        indicators = evaluate_monitoring_indicators(
            portfolio_profile, stock_profiles, holdings_dicts, custom_thresholds=payload.thresholds
        )
        historical_series = compute_historical_risk_series(holdings_dicts, portfolio_profile)

        # Calculate portfolio value and unrealized profit
        total_invested = sum(
            float(h.get("quantity", 1.0)) * float(h.get("buyPrice", 1.0)) for h in holdings_dicts
        )
        current_value = sum(
            float(h.get("quantity", 1.0))
            * (
                float(sp.current_price)
                if sp.current_price is not None
                else float(h.get("buyPrice", 1.0))
            )
            for h, sp in zip(holdings_dicts, stock_profiles, strict=False)
        )
        overall_ret = (
            ((current_value - total_invested) / total_invested) * 100.0
            if total_invested > 0
            else 0.0
        )

        # Largest holding
        largest_sym = "N/A"
        largest_wt = 0.0
        if total_invested > 0:
            for h in holdings_dicts:
                wt = (
                    (float(h["quantity"]) * float(h["buyPrice"])) / total_invested
                ) * 100.0
                if wt > largest_wt:
                    largest_wt = wt
                    largest_sym = str(h.get("symbol", "")).upper()

        top_sec_dict = (
            portfolio_profile.sector_exposure[0] if portfolio_profile.sector_exposure else {}
        )
        top_sec_name = str(top_sec_dict.get("sector", "N/A"))
        top_sec_wt = float(top_sec_dict.get("weight", 0.0))
        top_sec_status = str(top_sec_dict.get("allocation_status", "Balanced"))

        # Extract major correlated groups from pairwise correlations >= 0.50
        correlated_groups: list[CorrelatedHoldingGroup] = []
        corr_matrix = portfolio_profile.correlation_matrix
        symbols = list(corr_matrix.keys())
        clustered_syms: set[str] = set()

        for idx, sym1 in enumerate(symbols):
            if sym1 in clustered_syms:
                continue
            group = [sym1]
            pair_corrs: list[float] = []
            for sym2 in symbols[idx + 1 :]:
                rho = corr_matrix.get(sym1, {}).get(sym2)
                if rho is not None and rho >= 0.50:
                    group.append(sym2)
                    pair_corrs.append(rho)
                    clustered_syms.add(sym2)

            if len(group) > 1:
                clustered_syms.add(sym1)
                avg_rho = sum(pair_corrs) / len(pair_corrs)
                # Calculate aggregate weight
                agg_wt = sum(
                    (
                        (float(h["quantity"]) * float(h["buyPrice"]))
                        / total_invested
                        * 100.0
                    )
                    for h in holdings_dicts
                    if str(h.get("symbol", "")).upper() in group
                )
                correlated_groups.append(
                    CorrelatedHoldingGroup(
                        cluster_id=f"GRP-{len(correlated_groups) + 1}",
                        holding_symbols=group,
                        aggregate_weight=round(agg_wt, 1),
                        average_correlation=round(avg_rho, 2),
                        interpretation=(
                            f"Strong co-movement (mean ρ = {avg_rho:.2f}) among "
                            f"{', '.join(group)}. Combined position represents "
                            f"{agg_wt:.1f}% of portfolio capital."
                        ),
                    )
                )

        # Largest risk contributors
        risk_contributors = [
            {
                "symbol": str(e.get("symbol", "")),
                "risk_contribution_percent": float(e.get("risk_contribution_percent", 0.0)),
                "weight_percent": float(e.get("weight_percent", 0.0)),
                "sector": str(e.get("sector", "")),
                "is_amplified": float(e.get("risk_contribution_percent", 0.0))
                > float(e.get("weight_percent", 0.0)),
            }
            for e in portfolio_profile.risk_contributions[:5]
        ]

        # Structural changes
        structural_changes = list(portfolio_profile.summary_findings)
        if portfolio_profile.historical_risk_trend == "Elevating":
            structural_changes.insert(
                0,
                "Structural Alert: Short-term (1M) portfolio volatility is running higher than "
                "the 6M baseline, signalling accelerating risk momentum.",
            )

        # Build snapshot
        snapshot = StructuralMonitoringSnapshot(
            portfolio_value=round(current_value, 2),
            overall_return=round(overall_ret, 2),
            portfolio_risk_score=portfolio_profile.portfolio_risk_score,
            portfolio_classification=portfolio_profile.portfolio_classification,
            diversification_score=portfolio_profile.diversification_score,
            diversification_grade=portfolio_profile.diversification_grade,
            top_sector=top_sec_name,
            top_sector_weight=round(top_sec_wt, 1),
            top_sector_status=top_sec_status,
            largest_holding=largest_sym,
            largest_holding_weight=round(largest_wt, 1),
            correlated_groups=correlated_groups,
            largest_risk_contributors=risk_contributors,
            structural_changes=structural_changes,
            indicators=indicators,
            historical_risk_series=historical_series,
            persisted_history_count=0,
            data_freshness="Point-in-time Verified (Daily Adjusted Closes)",
        )

        # Anonymous analytical requests are deliberately non-persistent. Durable risk
        # history is available only through the owner-scoped portfolio endpoint.
        snapshot.persisted_history_count = 0

        return snapshot.to_dict()

    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Structural monitoring calculation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Structural monitoring is temporarily unavailable",
        ) from exc


@router.get("/risk-history")
def get_risk_history() -> dict[str, Any]:
    """Reject the retired server-global history surface."""
    raise HTTPException(
        status_code=http_status.HTTP_410_GONE,
        detail="Use the authenticated /portfolios/{portfolio_id}/risk-history endpoint",
    )


@router.post("/news-signals")
def get_news_signals(payload: ComprehensiveRiskRequest, _user: CurrentUser) -> dict[str, Any]:
    """Return decoupled modular news intelligence with verified sourced feeds."""
    from backend.app.news.service import NewsIntelligenceService

    service = NewsIntelligenceService(use_transformer=False)
    holdings_dicts = [h.model_dump() for h in payload.holdings]
    total_val = sum(float(h.get("quantity", 1.0)) * float(h.get("buyPrice", 1.0)) for h in holdings_dicts)
    for h in holdings_dicts:
        if total_val > 0:
            h["weight"] = (float(h.get("quantity", 1.0)) * float(h.get("buyPrice", 1.0))) / total_val
        else:
            h["weight"] = 1.0 / len(holdings_dicts) if holdings_dicts else 0.0
    intel = service.get_portfolio_news_intelligence(holdings_dicts)
    res = intel.model_dump()

    # Backward compatibility with existing Phase 3 contract consumers
    res["contract_version"] = "v1-modular-draft"
    res["architecture_status"] = "Verified News Intelligence (Phase 5)"
    res["portfolio_sentiment_average"] = intel.portfolio_sentiment_score
    res["high_impact_event_count"] = sum(
        1
        for a in intel.verified_articles
        for s in a.signals
        if s.event_category not in ("routine_coverage", "uncertain")
    )
    res["stock_signals"] = [
        {
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sentiment_average_7d": s.mean_sentiment_score,
            "sentiment_label": (
                s.dominant_sentiment
                if s.dominant_sentiment in ("positive", "negative")
                else "neutral"
            ),
            "news_volume_24h": s.article_count_24h,
            "news_volume_7d": s.article_count_7d,
            "sentiment_drift_7d": s.sentiment_drift_7d,
            "significant_events": [ev.upper() for ev in s.primary_event_categories],
            "news_risk_multiplier": s.heuristic_news_risk_multiplier,
            "headline_sample": [
                a.headline for a in intel.verified_articles if s.symbol in a.affected_holdings
            ][:2],
            "data_freshness": "Verified Live Feed",
        }
        for s in intel.holding_summaries
    ]
    res["sample_articles"] = [
        {
            "id": a.id,
            "symbol": a.affected_holdings[0] if a.affected_holdings else "PORTFOLIO",
            "headline": a.headline,
            "summary": a.snippet or a.headline,
            "publisher": a.publisher,
            "published_at": a.published_at,
            "sentiment_score": a.signals[0].sentiment_score if a.signals else 0.0,
            "sentiment_label": (
                a.signals[0].sentiment_label
                if a.signals and a.signals[0].sentiment_label in ("positive", "negative")
                else "neutral"
            ),
            "relevance_score": a.signals[0].sentiment_confidence if a.signals else 0.85,
            "source_url": a.url,
            "explanation": a.explanation,
            "what_the_news_is": a.what_the_news_is,
            "market_and_sector_impact": a.market_and_sector_impact,
            "actionable_advice": a.actionable_advice,
        }
        for a in intel.verified_articles[:8]
    ]
    return res
