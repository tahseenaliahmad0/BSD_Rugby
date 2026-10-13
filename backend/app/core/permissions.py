"""Squad-level permissions.

Roles are ordered: admin > analyst > coach > player. A superadmin is an admin everywhere.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db import get_db
from app.models import Event, Membership, Role, Squad, User, Video

ROLE_RANK: dict[Role, int] = {Role.PLAYER: 0, Role.COACH: 1, Role.ANALYST: 2, Role.ADMIN: 3}

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


def squad_role(db: Session, user: User, squad_id: uuid.UUID) -> Role | None:
    """The user's role in a squad, or None if they are not a member."""
    if user.is_superadmin:
        return Role.ADMIN
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.squad_id == squad_id)
    )
    return membership.role if membership else None


def has_role(role: Role | None, minimum: Role) -> bool:
    return role is not None and ROLE_RANK[role] >= ROLE_RANK[minimum]


def check_squad_role(db: Session, user: User, squad_id: uuid.UUID, minimum: Role) -> Role:
    """Raise 404 for non-members (do not reveal that the squad exists) and 403 for low roles."""
    role = squad_role(db, user, squad_id)
    if role is None:
        raise NOT_FOUND
    if not has_role(role, minimum):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to do that in this squad.",
        )
    return role


def require_squad(minimum: Role) -> Callable[..., Squad]:
    """Dependency factory: load the squad from the `squad_id` path parameter and check the role."""

    def dependency(
        squad_id: uuid.UUID,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> Squad:
        squad = db.get(Squad, squad_id)
        if squad is None:
            raise NOT_FOUND
        check_squad_role(db, user, squad_id, minimum)
        return squad

    return dependency


def require_event(minimum: Role) -> Callable[..., Event]:
    def dependency(
        event_id: uuid.UUID,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> Event:
        event = db.get(Event, event_id)
        if event is None:
            raise NOT_FOUND
        check_squad_role(db, user, event.squad_id, minimum)
        return event

    return dependency


def require_video(minimum: Role) -> Callable[..., Video]:
    def dependency(
        video_id: uuid.UUID,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> Video:
        video = db.get(Video, video_id)
        if video is None:
            raise NOT_FOUND
        check_squad_role(db, user, video.event.squad_id, minimum)
        return video

    return dependency


def accessible_squad_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Squads the user may read. None means "all" (superadmin)."""
    if user.is_superadmin:
        return None
    return list(db.scalars(select(Membership.squad_id).where(Membership.user_id == user.id)))
