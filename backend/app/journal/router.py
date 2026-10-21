"""Authenticated Journal (Research Notes & Investment Decisions) API."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import JournalDecision, JournalNote
from backend.app.db.session import get_session
from backend.app.journal.schemas import (
    JournalDecisionCreateInput,
    JournalDecisionResponse,
    JournalNoteCreateInput,
    JournalNoteResponse,
    JournalSyncRequest,
    JournalSyncResponse,
)

router = APIRouter(prefix="/journal", tags=["journal"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]


# ─── Research Notes Endpoints ───


@router.get("/notes", response_model=list[JournalNoteResponse])
def list_notes(
    session: DatabaseSession,
    user: CurrentUser,
    symbol: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JournalNoteResponse]:
    """Retrieve personal research notes for the authenticated user."""
    query = select(JournalNote).where(JournalNote.owner_id == user.id)
    if symbol:
        query = query.where(JournalNote.symbol == symbol.strip().upper())
    query = query.order_by(desc(JournalNote.updated_at)).offset(offset).limit(limit)

    notes = session.scalars(query).all()
    return [
        JournalNoteResponse(
            id=n.id,
            owner_id=n.owner_id,
            symbol=n.symbol,
            content=n.content,
            tags=n.tags,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in notes
    ]


@router.post(
    "/notes",
    response_model=JournalNoteResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def save_note(
    payload: JournalNoteCreateInput,
    session: DatabaseSession,
    user: CurrentUser,
) -> JournalNoteResponse:
    """Create or update a personal research note for the authenticated user."""
    note_id = payload.id or uuid4()

    # Ownership check if updating an existing record
    existing = session.scalar(select(JournalNote).where(JournalNote.id == note_id))
    if existing is not None:
        if existing.owner_id != user.id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        existing.symbol = payload.symbol
        existing.content = payload.content
        existing.tags = payload.tags
        session.commit()
        session.refresh(existing)
        target = existing
    else:
        new_note = JournalNote(
            id=note_id,
            owner_id=user.id,
            symbol=payload.symbol,
            content=payload.content,
            tags=payload.tags,
        )
        session.add(new_note)
        session.commit()
        session.refresh(new_note)
        target = new_note

    return JournalNoteResponse(
        id=target.id,
        owner_id=target.owner_id,
        symbol=target.symbol,
        content=target.content,
        tags=target.tags,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


@router.delete("/notes/{note_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> Response:
    """Delete a research note owned by the authenticated user."""
    note = session.scalar(
        select(JournalNote).where(JournalNote.id == note_id, JournalNote.owner_id == user.id)
    )
    if note is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    session.delete(note)
    session.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ─── Investment Decisions Endpoints ───


@router.get("/decisions", response_model=list[JournalDecisionResponse])
def list_decisions(
    session: DatabaseSession,
    user: CurrentUser,
    symbol: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JournalDecisionResponse]:
    """Retrieve personal investment decisions for the authenticated user."""
    query = select(JournalDecision).where(JournalDecision.owner_id == user.id)
    if symbol:
        query = query.where(JournalDecision.symbol == symbol.strip().upper())
    query = (
        query.order_by(desc(JournalDecision.decision_date), desc(JournalDecision.created_at))
        .offset(offset)
        .limit(limit)
    )

    decisions = session.scalars(query).all()
    return [
        JournalDecisionResponse(
            id=d.id,
            owner_id=d.owner_id,
            symbol=d.symbol,
            decision_type=d.decision_type,
            decision_date=d.decision_date,
            rationale=d.rationale,
            tags=d.tags,
            snapshot=d.snapshot,
            snapshot_id=d.snapshot_id,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in decisions
    ]


@router.post(
    "/decisions",
    response_model=JournalDecisionResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def save_decision(
    payload: JournalDecisionCreateInput,
    session: DatabaseSession,
    user: CurrentUser,
) -> JournalDecisionResponse:
    """Create or update a personal investment decision for the authenticated user."""
    decision_id = payload.id or uuid4()

    existing = session.scalar(select(JournalDecision).where(JournalDecision.id == decision_id))
    if existing is not None:
        if existing.owner_id != user.id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Decision not found",
            )
        existing.symbol = payload.symbol
        existing.decision_type = payload.decision_type
        existing.decision_date = payload.decision_date
        existing.rationale = payload.rationale
        existing.tags = payload.tags
        existing.snapshot = payload.snapshot
        existing.snapshot_id = payload.snapshot_id
        session.commit()
        session.refresh(existing)
        target = existing
    else:
        new_decision = JournalDecision(
            id=decision_id,
            owner_id=user.id,
            symbol=payload.symbol,
            decision_type=payload.decision_type,
            decision_date=payload.decision_date,
            rationale=payload.rationale,
            tags=payload.tags,
            snapshot=payload.snapshot,
            snapshot_id=payload.snapshot_id,
        )
        session.add(new_decision)
        session.commit()
        session.refresh(new_decision)
        target = new_decision

    return JournalDecisionResponse(
        id=target.id,
        owner_id=target.owner_id,
        symbol=target.symbol,
        decision_type=target.decision_type,
        decision_date=target.decision_date,
        rationale=target.rationale,
        tags=target.tags,
        snapshot=target.snapshot,
        snapshot_id=target.snapshot_id,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


@router.delete("/decisions/{decision_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_decision(
    decision_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> Response:
    """Delete an investment decision owned by the authenticated user."""
    decision = session.scalar(
        select(JournalDecision).where(
            JournalDecision.id == decision_id, JournalDecision.owner_id == user.id
        )
    )
    if decision is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )
    session.delete(decision)
    session.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ─── Offline-First / Client Migration Sync ───


@router.post("/sync", response_model=JournalSyncResponse)
def sync_journal_records(
    payload: JournalSyncRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> JournalSyncResponse:
    """Batch-upsert offline-first or previously client-side notes and decisions."""
    notes_count = 0
    decisions_count = 0

    for note_in in payload.notes:
        nid = note_in.id or uuid4()
        existing_n = session.scalar(
            select(JournalNote).where(JournalNote.id == nid, JournalNote.owner_id == user.id)
        )
        if existing_n:
            existing_n.symbol = note_in.symbol
            existing_n.content = note_in.content
            existing_n.tags = note_in.tags
        else:
            session.add(
                JournalNote(
                    id=nid,
                    owner_id=user.id,
                    symbol=note_in.symbol,
                    content=note_in.content,
                    tags=note_in.tags,
                )
            )
        notes_count += 1

    for dec_in in payload.decisions:
        did = dec_in.id or uuid4()
        existing_d = session.scalar(
            select(JournalDecision).where(
                JournalDecision.id == did, JournalDecision.owner_id == user.id
            )
        )
        if existing_d:
            existing_d.symbol = dec_in.symbol
            existing_d.decision_type = dec_in.decision_type
            existing_d.decision_date = dec_in.decision_date
            existing_d.rationale = dec_in.rationale
            existing_d.tags = dec_in.tags
            existing_d.snapshot = dec_in.snapshot
            existing_d.snapshot_id = dec_in.snapshot_id
        else:
            session.add(
                JournalDecision(
                    id=did,
                    owner_id=user.id,
                    symbol=dec_in.symbol,
                    decision_type=dec_in.decision_type,
                    decision_date=dec_in.decision_date,
                    rationale=dec_in.rationale,
                    tags=dec_in.tags,
                    snapshot=dec_in.snapshot,
                    snapshot_id=dec_in.snapshot_id,
                )
            )
        decisions_count += 1

    session.commit()
    return JournalSyncResponse(notes_synced=notes_count, decisions_synced=decisions_count)
