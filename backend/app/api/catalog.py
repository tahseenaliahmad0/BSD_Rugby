"""Seasons, opponents and players: simple per-squad lists."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_squad
from app.db import get_db
from app.models import Opponent, Player, Role, Season, Squad, User
from app.schemas.squad import (
    OpponentCreate,
    OpponentOut,
    OpponentUpdate,
    PlayerCreate,
    PlayerOut,
    PlayerUpdate,
    SeasonCreate,
    SeasonOut,
    SeasonUpdate,
)

router = APIRouter(tags=["catalog"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


# Seasons ---------------------------------------------------------------------------------
@router.get("/squads/{squad_id}/seasons", response_model=list[SeasonOut])
def list_seasons(
    squad: Squad = Depends(require_squad(Role.PLAYER)), db: Session = Depends(get_db)
) -> list[Season]:
    return list(
        db.scalars(
            select(Season)
            .where(Season.squad_id == squad.id)
            .order_by(Season.start_date.desc().nulls_last(), Season.name.desc())
        )
    )


@router.post(
    "/squads/{squad_id}/seasons", response_model=SeasonOut, status_code=status.HTTP_201_CREATED
)
def create_season(
    body: SeasonCreate,
    squad: Squad = Depends(require_squad(Role.ANALYST)),
    db: Session = Depends(get_db),
) -> Season:
    if db.scalar(select(Season).where(Season.squad_id == squad.id, Season.name == body.name)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A season with that name already exists."
        )
    season = Season(squad_id=squad.id, **body.model_dump())
    db.add(season)
    db.commit()
    return season


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
def update_season(
    season_id: uuid.UUID,
    body: SeasonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Season:
    season = db.get(Season, season_id)
    if season is None:
        raise NOT_FOUND
    check_squad_role(db, user, season.squad_id, Role.ANALYST)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(season, key, value)
    db.commit()
    return season


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(
    season_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    season = db.get(Season, season_id)
    if season is None:
        raise NOT_FOUND
    check_squad_role(db, user, season.squad_id, Role.ADMIN)
    db.delete(season)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Opponents --------------------------------------------------------------------------------
@router.get("/squads/{squad_id}/opponents", response_model=list[OpponentOut])
def list_opponents(
    squad: Squad = Depends(require_squad(Role.PLAYER)), db: Session = Depends(get_db)
) -> list[Opponent]:
    return list(
        db.scalars(select(Opponent).where(Opponent.squad_id == squad.id).order_by(Opponent.name))
    )


@router.post(
    "/squads/{squad_id}/opponents", response_model=OpponentOut, status_code=status.HTTP_201_CREATED
)
def create_opponent(
    body: OpponentCreate,
    squad: Squad = Depends(require_squad(Role.ANALYST)),
    db: Session = Depends(get_db),
) -> Opponent:
    if db.scalar(select(Opponent).where(Opponent.squad_id == squad.id, Opponent.name == body.name)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That opponent already exists."
        )
    opponent = Opponent(squad_id=squad.id, **body.model_dump())
    db.add(opponent)
    db.commit()
    return opponent


@router.patch("/opponents/{opponent_id}", response_model=OpponentOut)
def update_opponent(
    opponent_id: uuid.UUID,
    body: OpponentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Opponent:
    opponent = db.get(Opponent, opponent_id)
    if opponent is None:
        raise NOT_FOUND
    check_squad_role(db, user, opponent.squad_id, Role.ANALYST)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(opponent, key, value)
    db.commit()
    return opponent


@router.delete("/opponents/{opponent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opponent(
    opponent_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    opponent = db.get(Opponent, opponent_id)
    if opponent is None:
        raise NOT_FOUND
    check_squad_role(db, user, opponent.squad_id, Role.ADMIN)
    db.delete(opponent)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Players ----------------------------------------------------------------------------------
@router.get("/squads/{squad_id}/players", response_model=list[PlayerOut])
def list_players(
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
    season_id: uuid.UUID | None = None,
) -> list[Player]:
    query = select(Player).where(Player.squad_id == squad.id)
    if season_id is not None:
        query = query.where(Player.season_id == season_id)
    return list(db.scalars(query.order_by(Player.shirt_number.nulls_last(), Player.name)))


@router.post(
    "/squads/{squad_id}/players", response_model=PlayerOut, status_code=status.HTTP_201_CREATED
)
def create_player(
    body: PlayerCreate,
    squad: Squad = Depends(require_squad(Role.ANALYST)),
    db: Session = Depends(get_db),
) -> Player:
    if body.season_id is not None:
        season = db.get(Season, body.season_id)
        if season is None or season.squad_id != squad.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="That season is not in this squad."
            )
    player = Player(squad_id=squad.id, **body.model_dump())
    db.add(player)
    db.commit()
    return player


@router.patch("/players/{player_id}", response_model=PlayerOut)
def update_player(
    player_id: uuid.UUID,
    body: PlayerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Player:
    player = db.get(Player, player_id)
    if player is None:
        raise NOT_FOUND
    check_squad_role(db, user, player.squad_id, Role.ANALYST)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(player, key, value)
    db.commit()
    return player


@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(
    player_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    player = db.get(Player, player_id)
    if player is None:
        raise NOT_FOUND
    check_squad_role(db, user, player.squad_id, Role.ANALYST)
    db.delete(player)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
