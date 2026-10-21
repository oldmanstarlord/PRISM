"""FastAPI API routes for Phase 5 News Intelligence and NLP."""

from __future__ import annotations

from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.session import get_session
from backend.app.news.schemas import (
    NewsArticleCard,
    NewsEvaluationResult,
    NewsPortfolioRequest,
    PortfolioNewsIntelligence,
)
from backend.app.news.service import NewsIntelligenceService

router = APIRouter(prefix="/news", tags=["News Intelligence"])

DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]

# Singleton service instance with lazy transformer
_news_service = NewsIntelligenceService(use_transformer=False)


@router.get("/provider-status")
def get_provider_status() -> dict[str, str]:
    """Return verified news feed provider status, limits, and attribution notices."""
    return {
        "provider_name": _news_service.feed_provider.provider_name,
        "provider_status": _news_service.feed_provider.provider_status,
        "disclaimer": _news_service.feed_provider.terms_and_attribution_notice,
    }


@router.post("/portfolio", response_model=PortfolioNewsIntelligence)
def get_portfolio_news(
    payload: NewsPortfolioRequest,
    db: DatabaseSession,
    _user: CurrentUser,
) -> PortfolioNewsIntelligence:
    """Fetch and aggregate verified news intelligence for portfolio holdings."""
    holdings_dicts = [h.model_dump() for h in payload.holdings]
    return _news_service.get_portfolio_news_intelligence(holdings_dicts, db=db)


@router.get("/symbol/{symbol}", response_model=list[NewsArticleCard])
def get_symbol_news(
    symbol: Annotated[
        str,
        Path(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9&.-]+$"),
    ],
    db: DatabaseSession,
    _user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[NewsArticleCard]:
    """Retrieve verified articles and entity sentiment for a single NSE security."""
    raw = _news_service.feed_provider.fetch_articles_for_symbol(symbol, max_results=limit)
    if not raw:
        return []
    return _news_service.process_raw_articles(raw, db=db)


@router.post("/evaluate-labels", response_model=NewsEvaluationResult)
def evaluate_against_labels(
    _user: CurrentUser,
) -> NewsEvaluationResult:
    """Evaluate sentiment and entity-matching accuracy strictly on user ground-truth labels."""
    template_path = FilePath("data/evaluation/news_sentiment_label_template.csv")
    if not template_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Ground-truth label template is not available.",
        )
    try:
        return _news_service.evaluate_against_user_labels(str(template_path))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
