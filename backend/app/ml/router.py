"""FastAPI router for ML Risk Model inference and AI Insights."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.auth import require_user
from backend.app.db.models import Security, SecurityAlias
from backend.app.db.session import get_session
from backend.app.ml.schemas import (
    AnomalyDetectionResponse,
    ComprehensiveInsightsResponse,
    MarketRegimeResponse,
    MLHoldingSymbolsRequest,
    MLPortfolioRequest,
    ModelStatusResponse,
    ScoreValidationResponse,
    VolatilityForecastResponse,
)
from backend.app.ml.service import MlInferenceService

router = APIRouter(
    prefix="/ml",
    tags=["ml-insights"],
    dependencies=[Depends(require_user)],
)

DatabaseSession = Annotated[Session, Depends(get_session)]
_ml_service = MlInferenceService()


def _get_company_names(session: Session, symbols: list[str]) -> dict[str, str]:
    """Retrieve company names for provided symbols from securities table."""
    stmt = (
        select(SecurityAlias.symbol, Security.company_name)
        .join(Security, Security.id == SecurityAlias.security_id)
        .where(SecurityAlias.symbol.in_(symbols))
    )
    rows = session.execute(stmt).all()
    return {str(row[0]): str(row[1]) for row in rows}


@router.get("/status", response_model=ModelStatusResponse)
def get_model_status(session: DatabaseSession) -> ModelStatusResponse:
    """Return model status, training cutoff, version, and validation metrics vs baseline."""
    statuses = _ml_service.get_model_statuses(session)
    return ModelStatusResponse(models=statuses)


@router.post("/volatility-forecast", response_model=VolatilityForecastResponse)
def get_volatility_forecast(
    request: MLPortfolioRequest,
    session: DatabaseSession,
) -> VolatilityForecastResponse:
    """Point-in-time 21-day forward realized volatility forecast for portfolio & holdings."""
    symbols = [h.symbol for h in request.holdings]
    weights = [h.weight for h in request.holdings]
    res = _ml_service.get_volatility_insights(symbols, weights, session)
    return VolatilityForecastResponse(
        status=res["status"],
        portfolio_forecast=res.get("portfolio_forecast"),
        holdings_forecasts=res.get("holdings_forecasts", []),
        error=res.get("error") or res.get("portfolio_reason"),
    )


@router.get("/market-regime", response_model=MarketRegimeResponse)
def get_market_regime(session: DatabaseSession) -> MarketRegimeResponse:
    """Compute 2-state Markov-switching filtered regime probabilities on NIFTY 50."""
    res = _ml_service.get_market_regime_insights(session)
    return MarketRegimeResponse(
        status=res["status"],
        market_regime=res.get("market_regime"),
        error=res.get("error"),
    )


@router.post("/anomalies", response_model=AnomalyDetectionResponse)
def get_holdings_anomalies(
    request: MLHoldingSymbolsRequest,
    session: DatabaseSession,
) -> AnomalyDetectionResponse:
    """Detect statistical anomalies across holdings using Isolation Forest vs Robust Z-score."""
    company_names = _get_company_names(session, request.symbols)
    res = _ml_service.get_anomaly_insights(request.symbols, session, company_names=company_names)
    return AnomalyDetectionResponse(
        status=res["status"],
        anomaly_analysis=res.get("anomaly_analysis"),
        error=res.get("error"),
    )


@router.get("/risk-score-validation", response_model=ScoreValidationResponse)
def get_risk_score_validation(session: DatabaseSession) -> ScoreValidationResponse:
    """Walk-forward validation of heuristic 5-factor risk score against forward vol and drawdown."""
    res = _ml_service.get_risk_score_validation_insights([], session)
    return ScoreValidationResponse(
        status=res["status"],
        score_validation=res.get("score_validation"),
        error=res.get("error"),
    )


@router.post("/comprehensive-insights", response_model=ComprehensiveInsightsResponse)
def get_comprehensive_insights(
    request: MLPortfolioRequest,
    session: DatabaseSession,
) -> ComprehensiveInsightsResponse:
    """Unified payload powering the Phase 4 'AI Insights' tab."""
    symbols = [h.symbol for h in request.holdings]
    weights = [h.weight for h in request.holdings]
    company_names = _get_company_names(session, symbols)
    payload = _ml_service.get_comprehensive_ai_insights(
        symbols, weights, session, company_names=company_names
    )
    return ComprehensiveInsightsResponse(
        model_statuses=payload["model_statuses"],
        volatility=payload["volatility"],
        regime=payload["regime"],
        anomalies=payload["anomalies"],
        score_validation=payload["score_validation"],
        governance=payload["governance"],
    )
