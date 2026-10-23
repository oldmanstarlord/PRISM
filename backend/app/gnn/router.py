from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.auth import require_user
from backend.app.db.session import get_session
from backend.app.gnn import service
from backend.app.gnn.schemas import GnnPortfolioRequest

router = APIRouter(
    prefix="/gnn",
    tags=["gnn-structural-drift"],
    dependencies=[Depends(require_user)],
)
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("/status")
def get_status(session: DatabaseSession) -> dict[str, object]:
    return service.status(session)


@router.post("/portfolio-drift")
def get_portfolio_drift(
    request: GnnPortfolioRequest, session: DatabaseSession
) -> dict[str, object]:
    return service.portfolio_drift(session, request.symbols)


@router.get("/companies/{symbol}")
def get_company_history(
    symbol: str,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=260)] = 52,
) -> dict[str, object]:
    return service.company_history(session, symbol.strip().upper(), limit)


@router.get("/market-history")
def get_market_history(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=260)] = 52,
) -> dict[str, object]:
    return service.market_history(session, limit)
