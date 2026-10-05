"""Anonymous local-first API for session-only portfolio analytics."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from backend.app.db.session import get_session
from backend.app.portfolio_analytics.schemas import (
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
)
from backend.app.portfolio_analytics.service import analyze_portfolio

router = APIRouter(prefix="/portfolio-analysis", tags=["portfolio analysis"])
DatabaseSession = Annotated[Session, Depends(get_session)]


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
