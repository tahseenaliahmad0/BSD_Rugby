from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import get_current_user
from app.core.permissions import require_event, require_squad
from app.db import get_db
from app.models import Event, EventType, Opponent, Role, Season, Squad, User
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.services.serializers import event_out

router = APIRouter(tags=["events"])


def _check_season(db: Session, squad_id: uuid.UUID, season_id: uuid.UUID | None) -> None:
    if season_id is None:
        return
    season = db.get(Season, season_id)
    if season is None or season.squad_id != squad_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="That season is not in this squad."
        )


def _check_opponent(db: Session, squad_id: uuid.UUID, opponent_id: uuid.UUID | None) -> None:
    if opponent_id is None:
        return
    opponent = db.get(Opponent, opponent_id)
    if opponent is None or opponent.squad_id != squad_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="That opponent is not in this squad."
        )


@router.get("/squads/{squad_id}/events", response_model=list[EventOut])
def list_events(
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
    season_id: uuid.UUID | None = None,
    opponent_id: uuid.UUID | None = None,
    type: EventType | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[EventOut]:
    query = (
        select(Event)
        .where(Event.squad_id == squad.id)
        .options(selectinload(Event.opponent), selectinload(Event.videos))
        .order_by(Event.date.desc(), Event.created_at.desc())
        .limit(limit)
    )
    if season_id is not None:
        query = query.where(Event.season_id == season_id)
    if opponent_id is not None:
        query = query.where(Event.opponent_id == opponent_id)
    if type is not None:
        query = query.where(Event.type == type)
    if date_from is not None:
        query = query.where(Event.date >= date_from)
    if date_to is not None:
        query = query.where(Event.date <= date_to)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.outerjoin(Opponent, Event.opponent_id == Opponent.id).where(
            or_(
                Event.title.ilike(pattern),
                Event.competition.ilike(pattern),
                Event.venue.ilike(pattern),
                Opponent.name.ilike(pattern),
            )
        )
    return [event_out(e, include_videos=False) for e in db.scalars(query)]


@router.post(
    "/squads/{squad_id}/events", response_model=EventOut, status_code=status.HTTP_201_CREATED
)
def create_event(
    body: EventCreate,
    squad: Squad = Depends(require_squad(Role.ANALYST)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EventOut:
    _check_season(db, squad.id, body.season_id)
    _check_opponent(db, squad.id, body.opponent_id)
    opponent_id = body.opponent_id
    if opponent_id is None and body.opponent_name and body.opponent_name.strip():
        name = body.opponent_name.strip()
        opponent = db.scalar(
            select(Opponent).where(
                Opponent.squad_id == squad.id, func.lower(Opponent.name) == name.lower()
            )
        )
        if opponent is None:
            opponent = Opponent(squad_id=squad.id, name=name)
            db.add(opponent)
            db.flush()
        opponent_id = opponent.id
    data = body.model_dump(exclude={"opponent_name", "opponent_id"})
    event = Event(squad_id=squad.id, opponent_id=opponent_id, created_by=user.id, **data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event_out(event, include_videos=True)


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event: Event = Depends(require_event(Role.PLAYER))) -> EventOut:
    return event_out(event, include_videos=True)


@router.patch("/events/{event_id}", response_model=EventOut)
def update_event(
    body: EventUpdate,
    event: Event = Depends(require_event(Role.ANALYST)),
    db: Session = Depends(get_db),
) -> EventOut:
    data = body.model_dump(exclude_unset=True)
    if "season_id" in data:
        _check_season(db, event.squad_id, data["season_id"])
    if "opponent_id" in data:
        _check_opponent(db, event.squad_id, data["opponent_id"])
    for key, value in data.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event_out(event, include_videos=True)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event: Event = Depends(require_event(Role.ADMIN)), db: Session = Depends(get_db)
) -> Response:
    from app.services.storage import get_storage

    storage = get_storage()
    for video in event.videos:
        storage.remove_video_files(video.id)
    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
