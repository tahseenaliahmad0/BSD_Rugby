from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_squad, squad_role
from app.db import get_db
from app.models import Export, Role, Squad, User
from app.schemas.exports import ExportCreate, ExportOut
from app.services import exports as svc
from app.services import playlists as playlist_svc
from app.services.exports import ExportInputError
from app.services.storage import Storage, get_storage

router = APIRouter(tags=["exports"])


@router.get("/squads/{squad_id}/exports", response_model=list[ExportOut])
def list_exports(
    squad: Squad = Depends(require_squad(Role.PLAYER)), db: Session = Depends(get_db)
) -> list[ExportOut]:
    rows = db.scalars(
        select(Export)
        .where(Export.squad_id == squad.id)
        .order_by(Export.created_at.desc())
        .limit(200)
    )
    return [svc.export_out(db, e) for e in rows]


@router.post(
    "/squads/{squad_id}/exports", response_model=ExportOut, status_code=status.HTTP_202_ACCEPTED
)
def create_export(
    body: ExportCreate,
    squad: Squad = Depends(require_squad(Role.COACH)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ExportOut:
    if body.kind == "playlist" and body.playlist_id is not None:
        playlist = playlist_svc.load_playlist(db, body.playlist_id)
        role = squad_role(db, user, squad.id)
        if (
            playlist is None
            or playlist.squad_id != squad.id
            or not playlist_svc.can_view(playlist, user, role)
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    try:
        export = svc.create_export(db, squad.id, user, body, settings)
    except ExportInputError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return svc.export_out(db, export)


def _load(db: Session, export_id: uuid.UUID, user: User) -> tuple[Export, Role]:
    export = db.get(Export, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    role = check_squad_role(db, user, export.squad_id, Role.PLAYER)
    return export, role


@router.get("/exports/{export_id}", response_model=ExportOut)
def get_export(
    export_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ExportOut:
    export, _ = _load(db, export_id, user)
    return svc.export_out(db, export)


@router.delete("/exports/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_export(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
) -> Response:
    export, role = _load(db, export_id, user)
    if export.owner_id != user.id and role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the person who made this export can delete it.",
        )
    svc.remove_export(db, export, storage)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
