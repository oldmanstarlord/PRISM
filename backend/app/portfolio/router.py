"""Authenticated portfolio input API."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import Portfolio, PortfolioHolding, PortfolioSnapshot, Security
from backend.app.db.session import get_session
from backend.app.portfolio.schemas import (
    InputMode,
    PortfolioArchiveRequest,
    PortfolioCreateRequest,
    PortfolioDetail,
    PortfolioPreviewRequest,
    PortfolioPreviewResponse,
    PortfolioSummary,
    PreviewHolding,
)
from backend.app.portfolio.service import preview_portfolio

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]


def _owned_portfolio(session: Session, portfolio_id: UUID, owner_id: UUID) -> Portfolio:
    portfolio = session.scalar(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.owner_id == owner_id)
    )
    if portfolio is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    return portfolio


def _latest_snapshot(session: Session, portfolio_id: UUID) -> PortfolioSnapshot:
    snapshot = session.scalar(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioSnapshot.created_at), desc(PortfolioSnapshot.id))
        .limit(1)
    )
    if snapshot is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Portfolio has no saved snapshot",
        )
    return snapshot


def _summary(session: Session, portfolio: Portfolio) -> PortfolioSummary:
    snapshot = _latest_snapshot(session, portfolio.id)
    holding_count = session.scalar(
        select(func.count())
        .select_from(PortfolioHolding)
        .where(PortfolioHolding.snapshot_id == snapshot.id)
    )
    return PortfolioSummary(
        id=portfolio.id,
        name=portfolio.name,
        input_mode=cast(InputMode, portfolio.input_mode),
        currency=portfolio.currency,
        archived_at=portfolio.archived_at,
        latest_snapshot_id=snapshot.id,
        valuation_date=snapshot.valuation_date,
        holding_count=holding_count or 0,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
    )


def _detail(session: Session, portfolio: Portfolio) -> PortfolioDetail:
    summary = _summary(session, portfolio)
    snapshot = session.get(PortfolioSnapshot, summary.latest_snapshot_id)
    if snapshot is None:  # pragma: no cover - guarded by _summary
        raise RuntimeError("latest portfolio snapshot disappeared")
    rows = session.execute(
        select(PortfolioHolding, Security.company_name, Security.industry)
        .join(Security, Security.id == PortfolioHolding.security_id)
        .where(PortfolioHolding.snapshot_id == snapshot.id)
        .order_by(PortfolioHolding.symbol)
    ).all()
    holdings = [
        PreviewHolding(
            security_id=holding.security_id,
            symbol=holding.symbol,
            company_name=company_name,
            industry=industry,
            value=holding.quantity
            if holding.quantity is not None
            else cast(Decimal, holding.target_weight),
        )
        for holding, company_name, industry in rows
    ]
    cash_value = (
        snapshot.cash_amount
        if portfolio.input_mode == "quantities"
        else snapshot.cash_weight
    )
    return PortfolioDetail(
        **summary.model_dump(),
        owner_id=portfolio.owner_id,
        cash_value=cash_value,
        holdings=holdings,
    )


@router.post("/preview", response_model=PortfolioPreviewResponse)
def preview(
    request: PortfolioPreviewRequest,
    session: DatabaseSession,
    _user: CurrentUser,
) -> PortfolioPreviewResponse:
    return preview_portfolio(session, request)


@router.post("", response_model=PortfolioDetail, status_code=http_status.HTTP_201_CREATED)
def create_portfolio(
    request: PortfolioCreateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> PortfolioDetail:
    preview_result = preview_portfolio(session, request)
    if not preview_result.valid or preview_result.preview_fingerprint is None:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Portfolio validation failed", "errors": preview_result.errors},
        )
    if preview_result.preview_fingerprint != request.preview_fingerprint:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Portfolio changed after preview; preview it again before saving",
        )
    if preview_result.valuation_date is None:  # pragma: no cover - valid preview guarantees it
        raise RuntimeError("valid preview has no valuation date")

    portfolio = Portfolio(
        owner_id=user.id,
        name=request.name,
        input_mode=request.input_mode,
        currency="INR",
    )
    session.add(portfolio)
    session.flush()
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio.id,
        owner_id=user.id,
        valuation_date=preview_result.valuation_date,
        cash_amount=(
            preview_result.cash_value if request.input_mode == "quantities" else Decimal(0)
        ),
        cash_weight=(
            preview_result.cash_value if request.input_mode == "weights" else Decimal(0)
        ),
        input_fingerprint=preview_result.preview_fingerprint,
        source="csv",
    )
    session.add(snapshot)
    session.flush()
    for holding in preview_result.holdings:
        session.add(
            PortfolioHolding(
                snapshot_id=snapshot.id,
                owner_id=user.id,
                security_id=holding.security_id,
                symbol=holding.symbol,
                quantity=holding.value if request.input_mode == "quantities" else None,
                target_weight=holding.value if request.input_mode == "weights" else None,
            )
        )
    session.commit()
    return _detail(session, portfolio)


@router.get("", response_model=list[PortfolioSummary])
def list_portfolios(
    session: DatabaseSession,
    user: CurrentUser,
    include_archived: Annotated[bool, Query()] = False,
) -> list[PortfolioSummary]:
    query = select(Portfolio).where(Portfolio.owner_id == user.id)
    if not include_archived:
        query = query.where(Portfolio.archived_at.is_(None))
    portfolios = session.scalars(query.order_by(desc(Portfolio.updated_at))).all()
    return [_summary(session, portfolio) for portfolio in portfolios]


@router.get("/{portfolio_id}", response_model=PortfolioDetail)
def get_portfolio(
    portfolio_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> PortfolioDetail:
    return _detail(session, _owned_portfolio(session, portfolio_id, user.id))


@router.patch("/{portfolio_id}/archive", response_model=PortfolioSummary)
def archive_portfolio(
    portfolio_id: UUID,
    request: PortfolioArchiveRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> PortfolioSummary:
    portfolio = _owned_portfolio(session, portfolio_id, user.id)
    portfolio.archived_at = datetime.now(UTC) if request.archived else None
    session.commit()
    return _summary(session, portfolio)


@router.delete("/{portfolio_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> Response:
    portfolio = _owned_portfolio(session, portfolio_id, user.id)
    if portfolio.archived_at is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Archive the portfolio before permanently deleting it",
        )
    session.delete(portfolio)
    session.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
