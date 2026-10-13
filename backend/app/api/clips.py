"""Clip search and saved filters."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_squad
from app.db import get_db
from app.models import Role, SavedFilter, Squad, User
from app.schemas.clips import (
    SavedFilterIn,
    SavedFilterOut,
    SavedFilterUpdate,
    SearchIn,
    SearchOut,
)
from app.services import clips as svc

router = APIRouter(tags=["clips"])


@router.post("/squads/{squad_id}/clips/search", response_model=SearchOut)
def search_clips(
    body: SearchIn,
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
) -> SearchOut:
    total, tags = svc.search_tags(db, squad.id, body.filter, limit=body.limit, offset=body.offset)
    return SearchOut(total=total, clips=svc.clips_for_tags(db, tags))


def _filter_out(db: Session, item: SavedFilter) -> SavedFilterOut:
    out = SavedFilterOut.model_validate(item)
    if item.owner_id is not None:
        owner = db.get(User, item.owner_id)
        out.owner_name = owner.name if owner else None
    return out


def _load_filter(db: Session, filter_id: uuid.UUID, user: User, *, edit: bool) -> SavedFilter:
    item = db.get(SavedFilter, filter_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    role = check_squad_role(db, user, item.squad_id, Role.PLAYER)
    is_owner = item.owner_id == user.id
    if not (is_owner or item.is_shared or role == Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    if edit and not (is_owner or role == Role.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can change this filter."
        )
    return item


@router.get("/squads/{squad_id}/filters", response_model=list[SavedFilterOut])
def list_filters(
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SavedFilterOut]:
    """Your own filters plus the ones shared with the squad."""
    rows = db.scalars(
        select(SavedFilter)
        .where(SavedFilter.squad_id == squad.id)
        .where(or_(SavedFilter.owner_id == user.id, SavedFilter.is_shared.is_(True)))
        .order_by(SavedFilter.name)
    ).all()
    return [_filter_out(db, r) for r in rows]


@router.post(
    "/squads/{squad_id}/filters", response_model=SavedFilterOut, status_code=status.HTTP_201_CREATED
)
def create_filter(
    body: SavedFilterIn,
    squad: Squad = Depends(require_squad(Role.COACH)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedFilterOut:
    item = SavedFilter(
        squad_id=squad.id,
        owner_id=user.id,
        name=body.name,
        definition=body.definition.model_dump(mode="json"),
        is_shared=body.is_shared,
    )
    db.add(item)
    db.commit()
    return _filter_out(db, item)


@router.get("/filters/{filter_id}", response_model=SavedFilterOut)
def get_filter(
    filter_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SavedFilterOut:
    return _filter_out(db, _load_filter(db, filter_id, user, edit=False))


@router.patch("/filters/{filter_id}", response_model=SavedFilterOut)
def update_filter(
    filter_id: uuid.UUID,
    body: SavedFilterUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedFilterOut:
    item = _load_filter(db, filter_id, user, edit=True)
    if body.name is not None:
        item.name = body.name
    if body.definition is not None:
        item.definition = body.definition.model_dump(mode="json")
    if body.is_shared is not None:
        item.is_shared = body.is_shared
    db.commit()
    return _filter_out(db, item)


@router.delete("/filters/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter(
    filter_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    item = _load_filter(db, filter_id, user, edit=True)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
