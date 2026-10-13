"""Users only see data from squads they belong to, and roles limit what they can change."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.models import Squad, User
from tests.conftest import ApiClient, login


def _create_match(client: ApiClient, squad_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/squads/{squad_id}/events",
        json={"type": "match", "date": "2026-10-03", "opponent_name": "Harvard"},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_superadmin_creates_squad_and_becomes_admin(client: ApiClient, admin: User) -> None:
    login(client, admin.email)
    response = client.post(
        "/api/squads", json={"name": "Men's 1st XV", "sport_variant": "fifteens"}
    )
    assert response.status_code == 201
    squad = response.json()
    assert squad["my_role"] == "admin"
    assert client.get("/api/squads").json()[0]["id"] == squad["id"]
    duplicate = client.post("/api/squads", json={"name": "Men's 1st XV"})
    assert duplicate.status_code == 409


def test_non_superadmin_cannot_create_squad(client: ApiClient, analyst: User) -> None:
    login(client, analyst.email)
    assert client.post("/api/squads", json={"name": "Rogue squad"}).status_code == 403


def test_outsider_cannot_see_other_squad(
    client: ApiClient, squad: Squad, analyst: User, outsider: User
) -> None:
    login(client, analyst.email)
    match = _create_match(client, str(squad.id))
    client.post("/api/auth/logout")

    login(client, outsider.email)
    squads = client.get("/api/squads").json()
    assert [s["name"] for s in squads] == ["Women's 1st XV"]
    # Not 403: a non-member must not learn that the squad or match exists.
    assert client.get(f"/api/squads/{squad.id}").status_code == 404
    assert client.get(f"/api/squads/{squad.id}/events").status_code == 404
    assert client.get(f"/api/events/{match['id']}").status_code == 404
    assert client.get(f"/api/events/{match['id']}/videos").status_code == 404
    assert (
        client.post(f"/api/squads/{squad.id}/events", json={"date": "2026-01-01"}).status_code
        == 404
    )


def test_coach_can_view_but_not_edit(
    client: ApiClient, squad: Squad, analyst: User, coach: User
) -> None:
    login(client, analyst.email)
    match = _create_match(client, str(squad.id))
    season = client.post(f"/api/squads/{squad.id}/seasons", json={"name": "2026-27"})
    assert season.status_code == 201
    client.post("/api/auth/logout")

    login(client, coach.email)
    assert client.get(f"/api/squads/{squad.id}").json()["my_role"] == "coach"
    events = client.get(f"/api/squads/{squad.id}/events").json()
    assert [e["display_title"] for e in events] == ["vs Harvard"]
    assert client.get(f"/api/events/{match['id']}").status_code == 200
    assert client.get(f"/api/squads/{squad.id}/seasons").status_code == 200
    forbidden = client.post(f"/api/squads/{squad.id}/events", json={"date": "2026-01-01"})
    assert forbidden.status_code == 403
    assert "permission" in forbidden.json()["detail"].lower()
    assert client.patch(f"/api/events/{match['id']}", json={"venue": "Home"}).status_code == 403
    assert client.delete(f"/api/events/{match['id']}").status_code == 403
    assert client.post(f"/api/squads/{squad.id}/seasons", json={"name": "x"}).status_code == 403
    assert (
        client.post(
            f"/api/squads/{squad.id}/members", json={"email": "new@example.com", "role": "coach"}
        ).status_code
        == 403
    )


def test_analyst_can_manage_library_but_not_members(
    client: ApiClient, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    match = _create_match(client, str(squad.id))
    assert match["opponent_name"] == "Harvard"
    # Re-using the opponent name does not create a duplicate opponent.
    again = _create_match(client, str(squad.id))
    assert again["opponent_id"] == match["opponent_id"]
    opponents = client.get(f"/api/squads/{squad.id}/opponents").json()
    assert len(opponents) == 1

    updated = client.patch(f"/api/events/{match['id']}", json={"venue": "Home", "is_home": True})
    assert updated.status_code == 200
    assert updated.json()["venue"] == "Home"

    player = client.post(
        f"/api/squads/{squad.id}/players", json={"name": "A. Back", "shirt_number": 10}
    )
    assert player.status_code == 201

    # Deleting events and managing members needs an admin.
    assert client.delete(f"/api/events/{match['id']}").status_code == 403
    assert (
        client.post(
            f"/api/squads/{squad.id}/members", json={"email": "new@example.com", "role": "coach"}
        ).status_code
        == 403
    )
    assert client.get("/api/users").status_code == 403


def test_squad_admin_adds_members_and_search_filters(
    client: ApiClient, db: Session, squad: Squad, admin: User
) -> None:
    login(client, admin.email)
    created = client.post(
        f"/api/squads/{squad.id}/members",
        json={
            "email": "newcoach@example.com",
            "role": "coach",
            "name": "New Coach",
            "password": "a long enough password",
        },
    )
    assert created.status_code == 201, created.text
    missing = client.post(
        f"/api/squads/{squad.id}/members", json={"email": "ghost@example.com", "role": "coach"}
    )
    assert missing.status_code == 404
    members = client.get(f"/api/squads/{squad.id}/members").json()
    assert [m["email"] for m in members] == ["newcoach@example.com"]

    promoted = client.patch(
        f"/api/squads/{squad.id}/members/{created.json()['user_id']}", json={"role": "analyst"}
    )
    assert promoted.json()["role"] == "analyst"

    client.post(
        f"/api/squads/{squad.id}/events", json={"date": "2026-09-20", "opponent_name": "Yale"}
    )
    client.post(
        f"/api/squads/{squad.id}/events",
        json={"date": "2026-09-27", "type": "training", "title": "Lineout session"},
    )
    assert len(client.get(f"/api/squads/{squad.id}/events").json()) == 2
    assert len(client.get(f"/api/squads/{squad.id}/events", params={"q": "yale"}).json()) == 1
    assert (
        len(client.get(f"/api/squads/{squad.id}/events", params={"type": "training"}).json()) == 1
    )
    assert (
        len(client.get(f"/api/squads/{squad.id}/events", params={"date_from": "2026-09-25"}).json())
        == 1
    )

    client.post("/api/auth/logout")
    login(client, "newcoach@example.com", "a long enough password")
    assert client.get(f"/api/squads/{squad.id}").json()["my_role"] == "analyst"
