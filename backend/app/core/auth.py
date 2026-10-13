"""Session creation, lookup and cookie handling."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.security import hash_token, new_token
from app.db import get_db
from app.models import User, UserSession

SLIDING_REFRESH = timedelta(minutes=10)


def create_session(
    db: Session, user: User, *, user_agent: str | None, settings: Settings
) -> tuple[UserSession, str]:
    token = new_token()
    now = datetime.now(UTC)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=(user_agent or "")[:500] or None,
        expires_at=now + timedelta(days=settings.session_ttl_days),
    )
    db.add(session)
    db.flush()
    return session, token


def set_session_cookies(response: Response, token: str, settings: Settings) -> str:
    """Set the HTTP-only session cookie and a readable CSRF cookie. Returns the CSRF token."""
    max_age = settings.session_ttl_days * 24 * 3600
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    csrf = new_token()
    set_csrf_cookie(response, csrf, settings)
    return csrf


def set_csrf_cookie(response: Response, csrf: str, settings: Settings) -> None:
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def lookup_session(db: Session, token: str) -> UserSession | None:
    now = datetime.now(UTC)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None or session.expires_at <= now:
        return None
    if now - session.last_seen_at > SLIDING_REFRESH:
        session.last_seen_at = now
        session.expires_at = now + timedelta(days=get_settings().session_ttl_days)
        db.commit()
    return session


def revoke_session(db: Session, token: str) -> None:
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is not None:
        db.delete(session)
        db.commit()


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    session = lookup_session(db, token)
    if session is None:
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue."
        )
    return user


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only a site administrator can do that."
        )
    return user


def user_id_or_none(user: User | None) -> uuid.UUID | None:
    return user.id if user else None
