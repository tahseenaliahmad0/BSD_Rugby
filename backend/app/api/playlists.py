from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_squad, squad_role
from app.db import get_db
from app.models import Playlist, PlaylistItem, Role, SavedFilter, Squad, User
from app.schemas.clips import FilterDefinition
from app.schemas.playlists import (
    ItemsAdd,
    ItemUpdate,
    OrderIn,
    PlaylistCreate,
    PlaylistItemOut,
    PlaylistOut,
    PlaylistUpdate,
    SharesIn,
)
from app.services import playlists as svc
from app.services.playlists import PlaylistInputError

router = APIRouter(tags=["playlists"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


def _load(db: Session, playlist_id: uuid.UUID, user: User, *, edit: bool) -> tuple[Playlist, Role]:
    playlist = svc.load_playlist(db, playlist_id)
    if playlist is None:
        raise NOT_FOUND
    role = squad_role(db, user, playlist.squad_id)
    if role is None or not svc.can_view(playlist, user, role):
        raise NOT_FOUND
    if edit and not svc.can_edit(playlist, user, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the person who made this playlist (or a squad admin) can change it.",
        )
    return playlist, role


def _bad(exc: PlaylistInputError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/squads/{squad_id}/playlists", response_model=list[PlaylistOut])
def list_playlists(
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PlaylistOut]:
    role = squad_role(db, user, squad.id)
    return [
        svc.playlist_out(db, p, user, role, with_items=False)
        for p in svc.visible_playlists(db, squad.id, user, role)
    ]


@router.post(
    "/squads/{squad_id}/playlists", response_model=PlaylistOut, status_code=status.HTTP_201_CREATED
)
def create_playlist(
    body: PlaylistCreate,
    squad: Squad = Depends(require_squad(Role.COACH)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistOut:
    definition = body.filter
    if body.saved_filter_id is not None:
        saved = db.get(SavedFilter, body.saved_filter_id)
        if saved is None or saved.squad_id != squad.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown saved filter."
            )
        definition = definition or FilterDefinition.model_validate(saved.definition)
    playlist = Playlist(
        squad_id=squad.id,
        owner_id=user.id,
        name=body.name,
        description=body.description,
        saved_filter_id=body.saved_filter_id,
    )
    db.add(playlist)
    db.flush()
    playlist = svc.load_playlist(db, playlist.id) or playlist
    try:
        if definition is not None:
            svc.rebuild_from_filter(db, playlist, definition)
        if body.tag_ids:
            svc.add_tags(db, playlist, body.tag_ids)
        if body.ranges:
            svc.add_ranges(db, playlist, body.ranges)
    except PlaylistInputError as exc:
        db.rollback()
        raise _bad(exc) from exc
    db.commit()
    playlist = svc.load_playlist(db, playlist.id) or playlist
    return svc.playlist_out(db, playlist, user, squad_role(db, user, squad.id), with_items=True)


@router.get("/playlists/{playlist_id}", response_model=PlaylistOut)
def get_playlist(
    playlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> PlaylistOut:
    playlist, role = _load(db, playlist_id, user, edit=False)
    return svc.playlist_out(db, playlist, user, role, with_items=True)


@router.patch("/playlists/{playlist_id}", response_model=PlaylistOut)
def update_playlist(
    playlist_id: uuid.UUID,
    body: PlaylistUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistOut:
    playlist, role = _load(db, playlist_id, user, edit=True)
    if body.name is not None:
        playlist.name = body.name
    if "description" in body.model_fields_set:
        playlist.description = body.description
    if body.filter is not None:
        playlist.filter_definition = body.filter.model_dump(mode="json")
    db.commit()
    return svc.playlist_out(db, playlist, user, role, with_items=False)


@router.delete("/playlists/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    playlist, _ = _load(db, playlist_id, user, edit=True)
    db.delete(playlist)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/playlists/{playlist_id}/items", response_model=list[PlaylistItemOut])
def add_items(
    playlist_id: uuid.UUID,
    body: ItemsAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PlaylistItemOut]:
    playlist, _ = _load(db, playlist_id, user, edit=True)
    try:
        added = svc.add_tags(db, playlist, body.tag_ids) + svc.add_ranges(db, playlist, body.ranges)
    except PlaylistInputError as exc:
        db.rollback()
        raise _bad(exc) from exc
    db.commit()
    added_ids = {i.id for i in added}
    playlist = svc.load_playlist(db, playlist.id) or playlist
    return [i for i in svc.items_out(db, playlist) if i.id in added_ids]


@router.patch("/playlists/{playlist_id}/items/{item_id}", response_model=PlaylistItemOut)
def update_item(
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistItemOut:
    playlist, _ = _load(db, playlist_id, user, edit=True)
    item = next((i for i in playlist.items if i.id == item_id), None)
    if item is None:
        raise NOT_FOUND
    if "note" in body.model_fields_set:
        item.note = body.note
    if item.tag_id is None:
        if body.start_ms is not None:
            item.start_ms = body.start_ms
        if body.end_ms is not None:
            item.end_ms = body.end_ms
        if item.start_ms is not None and item.end_ms is not None and item.end_ms <= item.start_ms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="A clip must end after it starts."
            )
    db.commit()
    playlist = svc.load_playlist(db, playlist.id) or playlist
    return next(i for i in svc.items_out(db, playlist) if i.id == item_id)


@router.delete("/playlists/{playlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    playlist_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    playlist, _ = _load(db, playlist_id, user, edit=True)
    item = db.get(PlaylistItem, item_id)
    if item is None or item.playlist_id != playlist.id:
        raise NOT_FOUND
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/playlists/{playlist_id}/order", response_model=PlaylistOut)
def reorder_items(
    playlist_id: uuid.UUID,
    body: OrderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistOut:
    playlist, role = _load(db, playlist_id, user, edit=True)
    try:
        svc.reorder(playlist, body.item_ids)
    except PlaylistInputError as exc:
        raise _bad(exc) from exc
    db.commit()
    playlist = svc.load_playlist(db, playlist.id) or playlist
    return svc.playlist_out(db, playlist, user, role, with_items=True)


@router.post("/playlists/{playlist_id}/refresh", response_model=PlaylistOut)
def refresh_from_filter(
    playlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> PlaylistOut:
    playlist, role = _load(db, playlist_id, user, edit=True)
    definition_raw = playlist.filter_definition
    if definition_raw is None and playlist.saved_filter_id is not None:
        saved = db.get(SavedFilter, playlist.saved_filter_id)
        definition_raw = saved.definition if saved else None
    if definition_raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This playlist was not built from a filter.",
        )
    svc.rebuild_from_filter(db, playlist, FilterDefinition.model_validate(definition_raw))
    db.commit()
    playlist = svc.load_playlist(db, playlist.id) or playlist
    return svc.playlist_out(db, playlist, user, role, with_items=True)


@router.post(
    "/playlists/{playlist_id}/duplicate",
    response_model=PlaylistOut,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_playlist(
    playlist_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> PlaylistOut:
    playlist, role = _load(db, playlist_id, user, edit=False)
    check_squad_role(db, user, playlist.squad_id, Role.COACH)
    copy = svc.duplicate(db, playlist, user.id)
    db.commit()
    copy = svc.load_playlist(db, copy.id) or copy
    return svc.playlist_out(db, copy, user, role, with_items=True)


@router.put("/playlists/{playlist_id}/shares", response_model=PlaylistOut)
def set_shares(
    playlist_id: uuid.UUID,
    body: SharesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaylistOut:
    playlist, role = _load(db, playlist_id, user, edit=True)
    try:
        svc.set_shares(db, playlist, body.user_ids)
    except PlaylistInputError as exc:
        db.rollback()
        raise _bad(exc) from exc
    db.commit()
    playlist = svc.load_playlist(db, playlist.id) or playlist
    return svc.playlist_out(db, playlist, user, role, with_items=False)
