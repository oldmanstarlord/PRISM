"""Authenticated portfolio input API."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import (
    AuditEvent,
    Portfolio,
    PortfolioHolding,
    PortfolioRiskHistory,
    PortfolioSnapshot,
    PortfolioTransaction,
    Security,
    SecurityAlias,
)
from backend.app.db.session import get_session
from backend.app.portfolio.ledger import (
    LedgerTransactionInput,
    LedgerValidationError,
    export_csv_transactions,
    parse_csv_transactions,
    reconcile_ledger,
    replay_ledger,
)
from backend.app.portfolio.schemas import (
    AuditEventResponse,
    InputMode,
    PortfolioArchiveRequest,
    PortfolioCreateRequest,
    PortfolioDetail,
    PortfolioPreviewRequest,
    PortfolioPreviewResponse,
    PortfolioSummary,
    PreviewHolding,
    ReconciliationResponse,
    RiskHistoryResponse,
    TransactionBatchCreateRequest,
    TransactionCreateInput,
    TransactionResponse,
)
from backend.app.portfolio.service import preview_portfolio

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]


def _record_audit_event(
    session: Session,
    *,
    owner_id: UUID,
    event_type: str,
    entity_id: UUID,
    details: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            owner_id=owner_id,
            event_type=event_type,
            entity_type="portfolio",
            entity_id=entity_id,
            details=details,
        )
    )


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
        snapshot.cash_amount if portfolio.input_mode == "quantities" else snapshot.cash_weight
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
        owner_ref=str(user.id),
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
        cash_weight=(preview_result.cash_value if request.input_mode == "weights" else Decimal(0)),
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
    _record_audit_event(
        session,
        owner_id=user.id,
        event_type="portfolio.created",
        entity_id=portfolio.id,
        details={
            "snapshot_id": str(snapshot.id),
            "input_fingerprint": snapshot.input_fingerprint,
            "input_mode": portfolio.input_mode,
            "valuation_date": snapshot.valuation_date.isoformat(),
            "holding_count": len(preview_result.holdings),
        },
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


@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    session: DatabaseSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AuditEventResponse]:
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.owner_id == user.id)
        .order_by(desc(AuditEvent.created_at), desc(AuditEvent.id))
        .limit(limit)
    ).all()
    return [
        AuditEventResponse(
            id=event.id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            details=event.details,
            created_at=event.created_at,
        )
        for event in events
    ]


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
    _record_audit_event(
        session,
        owner_id=user.id,
        event_type="portfolio.archived" if request.archived else "portfolio.restored",
        entity_id=portfolio.id,
        details={"archived": request.archived},
    )
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
    _record_audit_event(
        session,
        owner_id=user.id,
        event_type="portfolio.deleted",
        entity_id=portfolio.id,
        details={"name": portfolio.name},
    )
    session.delete(portfolio)
    session.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.get("/{portfolio_id}/transactions", response_model=list[TransactionResponse])
def get_portfolio_transactions(
    portfolio_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[TransactionResponse]:
    _owned_portfolio(session, portfolio_id, user.id)
    tx_rows = session.scalars(
        select(PortfolioTransaction)
        .where(
            PortfolioTransaction.portfolio_id == portfolio_id,
            PortfolioTransaction.owner_id == user.id,
        )
        .order_by(desc(PortfolioTransaction.trade_date), desc(PortfolioTransaction.created_at))
    ).all()
    return [
        TransactionResponse(
            id=tx.id,
            portfolio_id=tx.portfolio_id,
            owner_id=tx.owner_id,
            transaction_type=tx.transaction_type,
            symbol=tx.symbol,
            trade_date=tx.trade_date,
            quantity=tx.quantity,
            price=tx.price,
            amount=tx.amount,
            fees=tx.fees,
            realized_pnl=tx.realized_pnl,
            notes=tx.notes,
            created_at=tx.created_at,
        )
        for tx in tx_rows
    ]


@router.post(
    "/{portfolio_id}/transactions",
    response_model=list[TransactionResponse],
    status_code=http_status.HTTP_201_CREATED,
)
def record_transactions(
    portfolio_id: UUID,
    payload: TransactionBatchCreateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[TransactionResponse]:
    portfolio = _owned_portfolio(session, portfolio_id, user.id)

    # 1. Load existing transactions
    existing_txs = session.scalars(
        select(PortfolioTransaction)
        .where(
            PortfolioTransaction.portfolio_id == portfolio_id,
            PortfolioTransaction.owner_id == user.id,
        )
        .order_by(PortfolioTransaction.trade_date.asc(), PortfolioTransaction.created_at.asc())
    ).all()

    ledger_inputs = [
        LedgerTransactionInput(
            id=str(tx.id),
            transaction_type=cast(Any, tx.transaction_type),
            trade_date=tx.trade_date,
            symbol=tx.symbol,
            quantity=tx.quantity,
            price=tx.price,
            amount=tx.amount,
            fees=tx.fees,
            notes=tx.notes,
        )
        for tx in existing_txs
    ]

    # 2. Convert incoming payload into ledger inputs
    new_db_records: list[PortfolioTransaction] = []
    for tx_in in payload.transactions:
        tx_id = uuid4()
        amt = tx_in.amount
        if amt is None and tx_in.quantity is not None and tx_in.price is not None:
            amt = tx_in.quantity * tx_in.price

        if amt is None:
            amt = Decimal("0")

        ledger_input = LedgerTransactionInput(
            id=str(tx_id),
            transaction_type=tx_in.transaction_type,
            trade_date=tx_in.trade_date,
            symbol=tx_in.symbol,
            quantity=tx_in.quantity,
            price=tx_in.price,
            amount=amt,
            fees=tx_in.fees,
            notes=tx_in.notes,
        )
        ledger_inputs.append(ledger_input)

        sec_id = None
        if tx_in.symbol:
            sec_alias = session.scalar(
                select(SecurityAlias).where(
                    SecurityAlias.symbol == tx_in.symbol.upper(),
                    SecurityAlias.exchange == "NSE",
                )
            )
            if sec_alias:
                sec_id = sec_alias.security_id

        db_rec = PortfolioTransaction(
            id=tx_id,
            portfolio_id=portfolio.id,
            owner_id=user.id,
            transaction_type=tx_in.transaction_type,
            security_id=sec_id,
            symbol=tx_in.symbol.upper() if tx_in.symbol else None,
            trade_date=tx_in.trade_date,
            quantity=tx_in.quantity,
            price=tx_in.price,
            amount=amt,
            fees=tx_in.fees,
            notes=tx_in.notes,
        )
        new_db_records.append(db_rec)

    # 3. Replay entire ledger atomically to validate consistency
    try:
        replay_ledger(ledger_inputs)
    except LedgerValidationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ledger integrity violation: {exc}",
        ) from exc

    # 4. Save new transactions
    for rec in new_db_records:
        session.add(rec)

    _record_audit_event(
        session,
        owner_id=user.id,
        event_type="portfolio.transactions_recorded",
        entity_id=portfolio.id,
        details={"count": len(new_db_records)},
    )
    session.commit()

    return [
        TransactionResponse(
            id=tx.id,
            portfolio_id=tx.portfolio_id,
            owner_id=tx.owner_id,
            transaction_type=tx.transaction_type,
            symbol=tx.symbol,
            trade_date=tx.trade_date,
            quantity=tx.quantity,
            price=tx.price,
            amount=tx.amount,
            fees=tx.fees,
            realized_pnl=tx.realized_pnl,
            notes=tx.notes,
            created_at=tx.created_at,
        )
        for tx in new_db_records
    ]


@router.get("/{portfolio_id}/reconciliation", response_model=ReconciliationResponse)
def get_portfolio_reconciliation(
    portfolio_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ReconciliationResponse:
    _owned_portfolio(session, portfolio_id, user.id)

    # 1. Load transactions and replay ledger
    tx_rows = session.scalars(
        select(PortfolioTransaction)
        .where(
            PortfolioTransaction.portfolio_id == portfolio_id,
            PortfolioTransaction.owner_id == user.id,
        )
        .order_by(PortfolioTransaction.trade_date.asc(), PortfolioTransaction.created_at.asc())
    ).all()

    ledger_inputs = [
        LedgerTransactionInput(
            id=str(tx.id),
            transaction_type=cast(Any, tx.transaction_type),
            trade_date=tx.trade_date,
            symbol=tx.symbol,
            quantity=tx.quantity,
            price=tx.price,
            amount=tx.amount,
            fees=tx.fees,
            notes=tx.notes,
        )
        for tx in tx_rows
    ]

    state = replay_ledger(ledger_inputs)

    # 2. Compare against latest snapshot if one exists
    latest_snap = session.scalar(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(desc(PortfolioSnapshot.created_at))
        .limit(1)
    )

    disp_cash = None
    disp_holdings = None
    if latest_snap:
        disp_cash = latest_snap.cash_amount
        holding_rows = session.scalars(
            select(PortfolioHolding).where(PortfolioHolding.snapshot_id == latest_snap.id)
        ).all()
        disp_holdings = {h.symbol: h.quantity for h in holding_rows if h.quantity is not None}

    report = reconcile_ledger(state, displayed_cash=disp_cash, displayed_holdings=disp_holdings)

    return ReconciliationResponse(
        is_reconciled=report.is_reconciled,
        derived_cash=report.derived_cash,
        derived_invested_cost=report.derived_invested_cost,
        derived_holdings_count=report.derived_holdings_count,
        realized_pnl=report.realized_pnl,
        unrealized_pnl=report.unrealized_pnl,
        total_net_deposits=report.total_net_deposits,
        total_dividends=report.total_dividends,
        total_fees=report.total_fees,
        derived_holdings=[h.to_dict() for h in state.holdings.values()],
        discrepancies=list(report.discrepancies),
    )


@router.post("/{portfolio_id}/transactions/import-csv", response_model=list[TransactionResponse])
def import_csv_transactions(
    portfolio_id: UUID,
    csv_text: Annotated[str, Body(max_length=1_048_576, media_type="text/csv")],
    session: DatabaseSession,
    user: CurrentUser,
) -> list[TransactionResponse]:
    portfolio = _owned_portfolio(session, portfolio_id, user.id)

    # Parse and validate CSV rows
    parsed, errors = parse_csv_transactions(csv_text)
    if errors:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV validation errors: {'; '.join(errors[:5])}",
        )

    # Batch create
    batch_req = TransactionBatchCreateRequest(
        transactions=[
            TransactionCreateInput(
                transaction_type=tx.transaction_type,
                trade_date=tx.trade_date,
                symbol=tx.symbol,
                quantity=tx.quantity,
                price=tx.price,
                amount=tx.amount,
                fees=tx.fees,
                notes=tx.notes,
            )
            for tx in parsed
        ]
    )
    return record_transactions(portfolio.id, batch_req, session, user)


@router.get("/{portfolio_id}/transactions/export-csv")
def export_csv_endpoint(
    portfolio_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> Response:
    _owned_portfolio(session, portfolio_id, user.id)
    tx_rows = session.scalars(
        select(PortfolioTransaction)
        .where(
            PortfolioTransaction.portfolio_id == portfolio_id,
            PortfolioTransaction.owner_id == user.id,
        )
        .order_by(PortfolioTransaction.trade_date.asc(), PortfolioTransaction.created_at.asc())
    ).all()

    ledger_inputs = [
        LedgerTransactionInput(
            id=str(tx.id),
            transaction_type=cast(Any, tx.transaction_type),
            trade_date=tx.trade_date,
            symbol=tx.symbol,
            quantity=tx.quantity,
            price=tx.price,
            amount=tx.amount,
            fees=tx.fees,
            notes=tx.notes,
        )
        for tx in tx_rows
    ]
    csv_data = export_csv_transactions(ledger_inputs)
    filename = f"portfolio_{portfolio_id}_transactions.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{portfolio_id}/risk-history", response_model=list[RiskHistoryResponse])
def get_portfolio_risk_history_route(
    portfolio_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[RiskHistoryResponse]:
    _owned_portfolio(session, portfolio_id, user.id)
    rows = session.scalars(
        select(PortfolioRiskHistory)
        .where(
            PortfolioRiskHistory.portfolio_id == portfolio_id,
            PortfolioRiskHistory.owner_id == user.id,
        )
        .order_by(PortfolioRiskHistory.valuation_date.asc())
    ).all()

    return [
        RiskHistoryResponse(
            id=r.id,
            portfolio_id=r.portfolio_id,
            valuation_date=r.valuation_date,
            portfolio_risk_score=float(r.portfolio_risk_score),
            portfolio_classification=r.portfolio_classification,
            annualized_volatility=float(r.annualized_volatility),
            downside_volatility=float(r.downside_volatility),
            max_drawdown=float(r.max_drawdown),
            diversification_score=float(r.diversification_score),
            effective_holdings=float(r.effective_holdings),
            top_sector=r.top_sector,
            top_sector_weight=float(r.top_sector_weight),
            largest_holding=r.largest_holding,
            largest_holding_weight=float(r.largest_holding_weight),
            indicators_summary=r.indicators_summary,
            computed_at=r.computed_at,
        )
        for r in rows
    ]
