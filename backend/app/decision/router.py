"""FastAPI router for the PRISM Stock Decision Engine.

Endpoint: POST /api/v1/portfolio/analyze

Accepts:
  - A list of holdings directly (for frontend use without portfolio persistence).
  - Optionally a saved portfolio_id to load holdings from the database.

Does NOT break existing portfolio, sector divergence, or ML routes.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import Portfolio, PortfolioHolding, PortfolioSnapshot, Security
from backend.app.db.session import get_session
from backend.app.decision.engine import analyze_portfolio_decisions
from backend.app.decision.schemas import PortfolioDecisionRequest, PortfolioDecisionResponse

router = APIRouter(prefix="/portfolio", tags=["decision engine"])
logger = logging.getLogger(__name__)

DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]


def _load_holdings_from_saved_portfolio(
    session: Session,
    portfolio_id: UUID,
    owner_id: UUID,
) -> list[dict[str, Any]]:
    """Load holdings from a persisted portfolio snapshot.

    Returns holding dicts compatible with the decision engine.
    Raises 404 if the portfolio is not found or not owned by the user.
    """
    portfolio = session.scalar(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_id == owner_id,
            Portfolio.archived_at.is_(None),
        )
    )
    if portfolio is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found or not accessible.",
        )

    snapshot = session.scalar(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioSnapshot.created_at))
        .limit(1)
    )
    if snapshot is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Portfolio has no saved snapshot.",
        )

    rows = session.execute(
        select(PortfolioHolding, Security.company_name, Security.industry, Security.sector)
        .join(Security, Security.id == PortfolioHolding.security_id)
        .where(PortfolioHolding.snapshot_id == snapshot.id)
        .order_by(PortfolioHolding.symbol)
    ).all()

    if not rows:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Portfolio snapshot has no holdings to analyze.",
        )

    # Compute total portfolio value for weight calculation
    total_value = sum(float(h.quantity or h.target_weight or 1.0) for h, *_ in rows)

    holdings: list[dict[str, Any]] = []
    for holding, company_name, industry, sector in rows:
        raw_value = float(holding.quantity or holding.target_weight or 1.0)
        weight = raw_value / total_value if total_value > 0 else 0.0
        holdings.append(
            {
                "symbol": holding.symbol,
                "company_name": company_name,
                "sector": sector or industry,
                "quantity": float(holding.quantity or 1.0),
                "buy_price": 1.0,  # buyPrice not persisted in snapshot; weight carries the info
                "weight": weight,
            }
        )

    return holdings


@router.post(
    "/analyze",
    response_model=PortfolioDecisionResponse,
    summary="Stock Decision Engine — SELL / HOLD / WAIT & WATCH",
    description=(
        "Analyzes every stock in the provided portfolio using three factors: "
        "existing five-factor ML risk score (60%), sector divergence (25%), "
        "and news sentiment (15%). Returns SELL / HOLD / WAIT & WATCH flags "
        "with full explainability. "
        "This endpoint is diagnostic only and does NOT constitute investment advice."
    ),
)
def analyze_portfolio(
    payload: PortfolioDecisionRequest,
    session: DatabaseSession,
) -> PortfolioDecisionResponse:
    """Analyze all provided holdings and assign decision flags."""
    try:
        holdings: list[dict[str, Any]] = [
            {
                "symbol": h.symbol,
                "company_name": h.company_name,
                "sector": h.sector,
                "quantity": h.quantity,
                "buy_price": h.buy_price,
                "weight": h.weight or 0.0,
            }
            for h in payload.holdings
        ]

        # If no weights provided, distribute equally
        any_weight = any(h.get("weight", 0) > 0 for h in holdings)
        if not any_weight:
            n = len(holdings)
            for h in holdings:
                h["weight"] = 1.0 / n if n > 0 else 0.0

        return analyze_portfolio_decisions(holdings, session)

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Decision engine failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Decision analysis failed; see server logs.",
        ) from exc


@router.post(
    "/analyze/saved",
    response_model=PortfolioDecisionResponse,
    summary="Stock Decision Engine — analyze a saved portfolio",
)
def analyze_saved_portfolio(
    session: DatabaseSession,
    user: CurrentUser,
    portfolio_id: Annotated[UUID, Query(description="ID of the saved portfolio to analyze")],
) -> PortfolioDecisionResponse:
    """Load holdings from a persisted portfolio and run the decision engine."""
    holdings = _load_holdings_from_saved_portfolio(session, portfolio_id, user.id)
    try:
        return analyze_portfolio_decisions(holdings, session)
    except Exception as exc:
        logger.error(
            "Decision engine failed for portfolio %s: %s", portfolio_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Decision analysis failed; see server logs.",
        ) from exc
