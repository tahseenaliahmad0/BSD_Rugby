from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import get_current_user, require_superadmin
from app.core.permissions import accessible_squad_ids, require_squad, squad_role
from app.core.security import hash_password
from app.db import get_db
from app.models import Membership, Role, Squad, User
from app.schemas.squad import MemberAdd, MemberOut, MemberUpdate, SquadCreate, SquadOut, SquadUpdate
from app.services.templates import ensure_default_templates

router = APIRouter(prefix="/squads", tags=["squads"])


def _squad_out(db: Session, squad: Squad, user: User) -> SquadOut:
    out = SquadOut.model_validate(squad)
    out.my_role = squad_role(db, user, squad.id)
    return out


@router.get("", response_model=list[SquadOut])
def list_squads(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[SquadOut]:
    ids = accessible_squad_ids(db, user)
    query = select(Squad).order_by(Squad.name)
    if ids is not None:
        query = query.where(Squad.id.in_(ids))
    return [_squad_out(db, s, user) for s in db.scalars(query)]


@router.post("", response_model=SquadOut, status_code=status.HTTP_201_CREATED)
def create_squad(
    body: SquadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
) -> SquadOut:
    if db.scalar(select(Squad).where(Squad.name == body.name)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A squad with that name already exists."
        )
    squad = Squad(name=body.name, sport_variant=body.sport_variant)
    db.add(squad)
    db.flush()
    db.add(Membership(user_id=user.id, squad_id=squad.id, role=Role.ADMIN))
    ensure_default_templates(db, squad.id, user.id)
    db.commit()
    return _squad_out(db, squad, user)


@router.get("/{squad_id}", response_model=SquadOut)
def get_squad(
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SquadOut:
    return _squad_out(db, squad, user)


@router.patch("/{squad_id}", response_model=SquadOut)
def update_squad(
    body: SquadUpdate,
    squad: Squad = Depends(require_squad(Role.ADMIN)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SquadOut:
    if body.name is not None:
        squad.name = body.name
    if body.sport_variant is not None:
        squad.sport_variant = body.sport_variant
    db.commit()
    return _squad_out(db, squad, user)


@router.get("/{squad_id}/members", response_model=list[MemberOut])
def list_members(
    squad: Squad = Depends(require_squad(Role.COACH)), db: Session = Depends(get_db)
) -> list[MemberOut]:
    memberships = db.scalars(
        select(Membership)
        .where(Membership.squad_id == squad.id)
        .options(selectinload(Membership.user))
    ).all()
    return [
        MemberOut(
            user_id=m.user_id,
            name=m.user.name,
            email=m.user.email,
            role=m.role,
            is_active=m.user.is_active,
        )
        for m in sorted(memberships, key=lambda m: m.user.name.lower())
    ]


@router.post("/{squad_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    body: MemberAdd,
    squad: Squad = Depends(require_squad(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> MemberOut:
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        if not body.name or not body.password:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account with that email. Give a name and a password to create one.",
            )
        user = User(name=body.name, email=email, password_hash=hash_password(body.password))
        db.add(user)
        db.flush()
    existing = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.squad_id == squad.id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That person is already in this squad."
        )
    membership = Membership(user_id=user.id, squad_id=squad.id, role=body.role)
    db.add(membership)
    db.commit()
    return MemberOut(
        user_id=user.id, name=user.name, email=user.email, role=body.role, is_active=user.is_active
    )


@router.patch("/{squad_id}/members/{user_id}", response_model=MemberOut)
def update_member(
    user_id: uuid.UUID,
    body: MemberUpdate,
    squad: Squad = Depends(require_squad(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> MemberOut:
    membership = db.scalar(
        select(Membership)
        .where(Membership.user_id == user_id, Membership.squad_id == squad.id)
        .options(selectinload(Membership.user))
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    membership.role = body.role
    db.commit()
    u = membership.user
    return MemberOut(
        user_id=u.id, name=u.name, email=u.email, role=membership.role, is_active=u.is_active
    )


@router.delete("/{squad_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: uuid.UUID,
    squad: Squad = Depends(require_squad(Role.ADMIN)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if user_id == user.id and not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove yourself."
        )
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user_id, Membership.squad_id == squad.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    db.delete(membership)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
