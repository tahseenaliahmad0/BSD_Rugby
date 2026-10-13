from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_event
from app.db import get_db
from app.models import Event, Role, Tag, User
from app.schemas.tags import (
    BatchOut,
    MergeIn,
    SplitIn,
    TagBatch,
    TagConflictOut,
    TagCreate,
    TagOut,
    TagPair,
    TagUpdate,
)
from app.services import tags as svc
from app.services.tags import TagConflictError, TagInputError

router = APIRouter(tags=["tags"])

CONFLICT_MESSAGE = "This tag was changed by someone else. Your screen now shows their version."


def conflict_response(exc: TagConflictError) -> JSONResponse:
    body = TagConflictOut(
        detail=CONFLICT_MESSAGE if exc.current else "This tag was deleted by someone else.",
        current=svc.tag_out(exc.current) if exc.current else None,
    )
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=body.model_dump(mode="json"))


def _load(db: Session, tag_id: uuid.UUID, user: User, minimum: Role) -> tuple[Tag, Event]:
    tag = svc.load_tag(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    event = db.get(Event, tag.event_id)
    assert event is not None
    check_squad_role(db, user, event.squad_id, minimum)
    return tag, event


@router.get("/events/{event_id}/tags", response_model=list[TagOut])
def list_tags(
    event: Event = Depends(require_event(Role.PLAYER)), db: Session = Depends(get_db)
) -> list[TagOut]:
    return [svc.tag_out(t) for t in svc.list_event_tags(db, event.id)]


@router.post("/events/{event_id}/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    body: TagCreate,
    event: Event = Depends(require_event(Role.ANALYST)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TagOut:
    try:
        tag = svc.create_tag(db, event, body, user.id)
    except TagInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return svc.tag_out(tag)


@router.post("/events/{event_id}/tags/batch", response_model=BatchOut)
def batch_tags(
    body: TagBatch,
    event: Event = Depends(require_event(Role.ANALYST)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchOut | JSONResponse:
    created: list[TagOut] = []
    deleted: list[uuid.UUID] = []
    try:
        for ref in body.delete:
            tag = svc.load_tag(db, ref.id)
            if tag is None or tag.event_id != event.id:
                continue
            svc.delete_tag(db, tag, ref.version)
            deleted.append(ref.id)
        for item in body.create:
            created.append(svc.tag_out(svc.create_tag(db, event, item, user.id)))
    except TagInputError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TagConflictError as exc:
        return conflict_response(exc)
    db.commit()
    return BatchOut(created=created, deleted=deleted)


@router.post("/events/{event_id}/tags/merge", response_model=TagOut)
def merge_tags(
    body: MergeIn,
    event: Event = Depends(require_event(Role.ANALYST)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TagOut | JSONResponse:
    try:
        tag = svc.merge_tags(db, body.tags, event, user.id)
    except TagInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TagConflictError as exc:
        return conflict_response(exc)
    db.commit()
    return svc.tag_out(tag)


@router.get("/tags/{tag_id}", response_model=TagOut)
def get_tag(
    tag_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TagOut:
    tag, _ = _load(db, tag_id, user, Role.PLAYER)
    return svc.tag_out(tag)


@router.patch("/tags/{tag_id}", response_model=TagOut, responses={409: {"model": TagConflictOut}})
def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TagOut | JSONResponse:
    tag, event = _load(db, tag_id, user, Role.ANALYST)
    try:
        updated = svc.update_tag(db, tag, body, event.squad_id, user.id)
    except TagInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TagConflictError as exc:
        return conflict_response(exc)
    db.commit()
    return svc.tag_out(updated)


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": TagConflictOut}},
)
def delete_tag(
    tag_id: uuid.UUID,
    request: Request,
    version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    tag, _ = _load(db, tag_id, user, Role.ANALYST)
    try:
        svc.delete_tag(db, tag, version)
    except TagConflictError as exc:
        return conflict_response(exc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tags/{tag_id}/split", response_model=TagPair, responses={409: {"model": TagConflictOut}}
)
def split_tag(
    tag_id: uuid.UUID,
    body: SplitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TagPair | JSONResponse:
    tag, _ = _load(db, tag_id, user, Role.ANALYST)
    try:
        left, right = svc.split_tag(db, tag, body.version, body.at_ms, user.id)
    except TagInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TagConflictError as exc:
        return conflict_response(exc)
    db.commit()
    return TagPair(left=svc.tag_out(left), right=svc.tag_out(right))
