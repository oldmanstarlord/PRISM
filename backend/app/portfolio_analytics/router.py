"""Anonymous local-first API for session-only portfolio analytics and stock-level risk."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.session import get_session
from backend.app.portfolio_analytics.news_signals import generate_modular_news_preview
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
    load_persisted_risk_history,
    persist_risk_snapshot,
)

router = APIRouter(prefix="/portfolio-analysis", tags=["portfolio analysis"])
DatabaseSession = Annotated[Session, Depends(get_session)]


class HoldingRiskInput(BaseModel):
    symbol: str = Field(min_length=1)
    companyName: str | None = None
    sector: str | None = None
    quantity: float = Field(default=1.0, gt=0)
    buyPrice: float = Field(default=1.0, gt=0)
    buyDate: str | None = None
    exchange: str = "NSE"


class ComprehensiveRiskRequest(BaseModel):
    holdings: list[HoldingRiskInput] = Field(min_length=1, max_length=150)


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
            "stock_profiles": [p.to_dict() for p in stock_profiles],
            "portfolio_profile": portfolio_profile.to_dict(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
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
            portfolio_profile, stock_profiles, holdings_dicts
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
                    (float(h.get("quantity", 1.0)) * float(h.get("buyPrice", 1.0))) / total_invested
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
                rho = corr_matrix.get(sym1, {}).get(sym2, 0.0)
                if rho >= 0.50:
                    group.append(sym2)
                    pair_corrs.append(rho)
                    clustered_syms.add(sym2)

            if len(group) > 1:
                clustered_syms.add(sym1)
                avg_rho = sum(pair_corrs) / len(pair_corrs) if pair_corrs else 0.50
                # Calculate aggregate weight
                agg_wt = sum(
                    (
                        (float(h.get("quantity", 1.0)) * float(h.get("buyPrice", 1.0)))
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

        # Auto-persist calculation to history store
        history_count = persist_risk_snapshot(snapshot.to_dict())
        snapshot.persisted_history_count = history_count

        return snapshot.to_dict()

    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/risk-history")
def get_risk_history() -> dict[str, Any]:
    """Retrieve saved portfolio risk calculations from persistent storage."""
    history = load_persisted_risk_history()
    return {
        "count": len(history),
        "history": history,
    }


@router.post("/news-signals")
def get_news_signals(payload: ComprehensiveRiskRequest) -> dict[str, Any]:
    """Return decoupled modular news intelligence and sentiment signals preview."""
    holdings_dicts = [h.model_dump() for h in payload.holdings]
    summary = generate_modular_news_preview(holdings_dicts)
    return summary.model_dump()
