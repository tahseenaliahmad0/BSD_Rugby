"""Test fixtures: a migrated test database, a FastAPI client and helper factories.

The test database URL comes from TEST_DATABASE_URL (default rugby_test on localhost).
Tables are truncated between tests. Celery runs tasks inline (eager) so the upload to
transcode path is exercised without a worker.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+pg8000://rugby:rugby@localhost:5432/rugby_test"
)
_STORAGE = tempfile.mkdtemp(prefix="rugby-test-storage-")

# Settings are cached on first use, so the environment must be set before importing the app.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DB_URL,
        "STORAGE_ROOT": _STORAGE,
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "COOKIE_SECURE": "false",
        "TRANSCODE_ENCODER": "libx264",
        "TRANSCODE_PRESET": "ultrafast",
        "THUMBNAIL_INTERVAL_S": "2",
    }
)

from alembic.config import Config  # noqa: E402

from alembic import command  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import get_engine, get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Membership, Role, Squad, User  # noqa: E402

CSRF_HEADER = get_settings().csrf_header_name
CSRF_COOKIE = get_settings().csrf_cookie_name


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    engine = get_engine()
    names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def storage_root() -> Path:
    return Path(_STORAGE)


class ApiClient(TestClient):
    """TestClient that sends the CSRF header automatically once the cookie is set."""

    def request(self, method: str, url: str, **kwargs):  # type: ignore[no-untyped-def]
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf = self.cookies.get(CSRF_COOKIE)
            if csrf:
                headers = dict(kwargs.pop("headers", None) or {})
                headers.setdefault(CSRF_HEADER, csrf)
                kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture
def client() -> Iterator[ApiClient]:
    with ApiClient(app, base_url="http://testserver") as c:
        yield c


def make_user(
    db: Session,
    *,
    email: str,
    password: str = "correct horse battery",
    name: str | None = None,
    superadmin: bool = False,
) -> User:
    user = User(
        name=name or email.split("@")[0].title(),
        email=email.lower(),
        password_hash=hash_password(password),
        is_superadmin=superadmin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_squad(db: Session, name: str | None = None) -> Squad:
    squad = Squad(name=name or f"Squad {uuid.uuid4().hex[:6]}")
    db.add(squad)
    db.commit()
    db.refresh(squad)
    return squad


def add_member(db: Session, user: User, squad: Squad, role: Role) -> Membership:
    membership = Membership(user_id=user.id, squad_id=squad.id, role=role)
    db.add(membership)
    db.commit()
    return membership


def login(client: ApiClient, email: str, password: str = "correct horse battery") -> dict[str, Any]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


@pytest.fixture
def admin(db: Session) -> User:
    return make_user(db, email="admin@example.com", superadmin=True)


@pytest.fixture
def squad(db: Session) -> Squad:
    return make_squad(db, "Men's 1st XV")


@pytest.fixture
def analyst(db: Session, squad: Squad) -> User:
    user = make_user(db, email="analyst@example.com")
    add_member(db, user, squad, Role.ANALYST)
    return user


@pytest.fixture
def coach(db: Session, squad: Squad) -> User:
    user = make_user(db, email="coach@example.com")
    add_member(db, user, squad, Role.COACH)
    return user


@pytest.fixture
def outsider(db: Session) -> User:
    """A user with no membership in `squad`."""
    other = make_squad(db, "Women's 1st XV")
    user = make_user(db, email="outsider@example.com")
    add_member(db, user, other, Role.ADMIN)
    return user
