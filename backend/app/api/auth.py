from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.core.auth import (
    clear_session_cookies,
    create_session,
    get_current_user,
    revoke_session,
    set_csrf_cookie,
    set_session_cookies,
)
from app.core.security import hash_password, password_needs_rehash, verify_password
from app.db import get_db
from app.models import Membership, User
from app.schemas.auth import LoginIn, MembershipSummary, MeOut, PasswordChange, UserOut
from app.schemas.common import Message

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(db: Session, user: User, csrf_token: str) -> MeOut:
    memberships = db.scalars(
        select(Membership)
        .where(Membership.user_id == user.id)
        .options(selectinload(Membership.squad))
    ).all()
    return MeOut(
        **UserOut.model_validate(user).model_dump(),
        memberships=[
            MembershipSummary(squad_id=m.squad_id, squad_name=m.squad.name, role=m.role)
            for m in sorted(memberships, key=lambda m: m.squad.name.lower())
        ],
        csrf_token=csrf_token,
    )


@router.post("/login", response_model=MeOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MeOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That email and password do not match.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled."
        )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    _, token = create_session(
        db, user, user_agent=request.headers.get("user-agent"), settings=settings
    )
    db.commit()
    csrf = set_session_cookies(response, token, settings)
    return _me(db, user, csrf)


@router.post("/logout", response_model=Message)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Message:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        revoke_session(db, token)
    clear_session_cookies(response, settings)
    return Message(detail="Signed out.")


@router.get("/me", response_model=MeOut)
def me(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MeOut:
    csrf = request.cookies.get(settings.csrf_cookie_name)
    if not csrf:
        from app.core.security import new_token

        csrf = new_token()
        set_csrf_cookie(response, csrf, settings)
    return _me(db, user, csrf)


@router.put("/password", response_model=Message)
def change_password(
    body: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Your current password is wrong."
        )
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return Message(detail="Password changed.")
