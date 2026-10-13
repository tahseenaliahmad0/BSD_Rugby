from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from tests.conftest import CSRF_COOKIE, CSRF_HEADER, ApiClient, login, make_user


def test_argon2_hashes_verify_and_differ() -> None:
    h1 = hash_password("secret-pass-123")
    h2 = hash_password("secret-pass-123")
    assert h1 != h2
    assert h1.startswith("$argon2id$")
    assert verify_password(h1, "secret-pass-123")
    assert not verify_password(h1, "wrong")
    assert not verify_password("not a hash", "x")


def test_me_requires_login(client: ApiClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "sign in" in response.json()["detail"].lower()


def test_login_sets_httponly_session_cookie_and_csrf_cookie(client: ApiClient, db: Session) -> None:
    make_user(db, email="Coach@Example.com", password="correct horse battery")
    response = client.post(
        "/api/auth/login", json={"email": "coach@example.com", "password": "correct horse battery"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "coach@example.com"
    assert body["csrf_token"]
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert "rugby_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    # The CSRF cookie must be readable by the browser script, so it is not HttpOnly.
    csrf_line = next(line for line in set_cookie.split("\n") if line.startswith(CSRF_COOKIE))
    assert "HttpOnly" not in csrf_line

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "coach@example.com"


def test_wrong_password_and_disabled_account(client: ApiClient, db: Session) -> None:
    user = make_user(db, email="x@example.com", password="correct horse battery")
    bad = client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert unknown.status_code == 401
    user.is_active = False
    db.commit()
    disabled = client.post(
        "/api/auth/login", json={"email": "x@example.com", "password": "correct horse battery"}
    )
    assert disabled.status_code == 403


def test_logout_revokes_session(client: ApiClient, db: Session) -> None:
    make_user(db, email="x@example.com")
    login(client, "x@example.com")
    session_cookie = client.cookies.get("rugby_session")
    assert session_cookie
    assert client.post("/api/auth/logout").status_code == 200
    # Even if the browser kept the cookie, the server no longer accepts it.
    client.cookies.set("rugby_session", session_cookie)
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_header_required_for_state_changes(client: ApiClient, db: Session) -> None:
    make_user(db, email="admin@example.com", superadmin=True)
    login(client, "admin@example.com")
    csrf = client.cookies.get(CSRF_COOKIE)
    assert csrf

    # Missing header: rejected before reaching the route.
    response = client.post("/api/squads", json={"name": "A"}, headers={CSRF_HEADER: ""})
    assert response.status_code == 403
    assert "reload" in response.json()["detail"].lower()

    # Wrong header: rejected.
    response = client.post("/api/squads", json={"name": "A"}, headers={CSRF_HEADER: "bogus"})
    assert response.status_code == 403

    # Matching header: accepted.
    response = client.post("/api/squads", json={"name": "A"}, headers={CSRF_HEADER: csrf})
    assert response.status_code == 201

    # Safe methods never need it.
    assert client.get("/api/squads").status_code == 200


def test_change_password(client: ApiClient, db: Session) -> None:
    make_user(db, email="x@example.com", password="correct horse battery")
    login(client, "x@example.com")
    wrong = client.put(
        "/api/auth/password",
        json={"current_password": "bad", "new_password": "new password 123"},
    )
    assert wrong.status_code == 400
    ok = client.put(
        "/api/auth/password",
        json={"current_password": "correct horse battery", "new_password": "new password 123"},
    )
    assert ok.status_code == 200
    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login", json={"email": "x@example.com", "password": "new password 123"}
        ).status_code
        == 200
    )


def test_health(client: ApiClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
