"""Playlists: from a filter, hand-picked, ranges, reorder, notes, duplicate, refresh, sharing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Role, Squad, User
from tests.conftest import ApiClient, add_member, login, make_user


def _seed(client: ApiClient, squad: Squad) -> dict[str, Any]:
    m1 = client.post(
        f"/api/squads/{squad.id}/events", json={"date": "2026-10-03", "opponent_name": "Yale"}
    ).json()
    m2 = client.post(
        f"/api/squads/{squad.id}/events", json={"date": "2026-10-10", "opponent_name": "Brown"}
    ).json()
    tags = {}
    for key, (event, code, start, outcome) in {
        "a": (m1, "Lineout", 1000, "Lost"),
        "b": (m1, "Lineout", 5000, "Won"),
        "c": (m2, "Lineout", 2000, "Lost"),
        "d": (m2, "Scrum", 3000, "Lost"),
    }.items():
        r = client.post(
            f"/api/events/{event['id']}/tags",
            json={
                "code": code,
                "start_ms": start,
                "end_ms": start + 4000,
                "descriptors": {"outcome": outcome},
            },
        )
        assert r.status_code == 201, r.text
        tags[key] = r.json()
    return {"m1": m1, "m2": m2, "tags": tags}


def test_playlist_from_filter_refresh_items_order_notes_duplicate(
    client: ApiClient, db: Session, squad: Squad, analyst: User, coach: User
) -> None:
    login(client, analyst.email)
    data = _seed(client, squad)
    client.post("/api/auth/logout")

    login(client, coach.email)
    sid = str(squad.id)
    created = client.post(
        f"/api/squads/{sid}/playlists",
        json={
            "name": "Lost lineouts",
            "filter": {"codes": ["Lineout"], "descriptors": {"outcome": ["Lost"]}},
        },
    )
    assert created.status_code == 201, created.text
    playlist = created.json()
    assert playlist["can_edit"] and playlist["owner_name"] == coach.name
    assert [i["tag_id"] for i in playlist["items"]] == [
        data["tags"]["c"]["id"],
        data["tags"]["a"]["id"],
    ]
    clip = playlist["items"][0]["clip"]
    assert clip["event"]["display_title"] == "vs Brown" and clip["code"] == "Lineout"
    assert clip["start_ms"] == 2000 and clip["video"] is None
    pid = playlist["id"]

    # Notes, order and hand-picked additions.
    first = playlist["items"][0]
    noted = client.patch(
        f"/api/playlists/{pid}/items/{first['id']}", json={"note": "Overthrown at the back"}
    )
    assert noted.json()["note"] == "Overthrown at the back"
    added = client.post(
        f"/api/playlists/{pid}/items",
        json={
            "tag_ids": [data["tags"]["b"]["id"]],
            "ranges": [
                {
                    "event_id": data["m1"]["id"],
                    "start_ms": 60000,
                    "end_ms": 65000,
                    "note": "Big hit",
                }
            ],
        },
    )
    assert added.status_code == 200, added.text
    assert [i["clip"]["label"] for i in added.json()] == ["Lineout", "Big hit"]
    items = client.get(f"/api/playlists/{pid}").json()["items"]
    assert len(items) == 4
    reordered = client.put(
        f"/api/playlists/{pid}/order", json={"item_ids": [i["id"] for i in reversed(items)]}
    )
    assert reordered.status_code == 200
    assert [i["id"] for i in reordered.json()["items"]] == [i["id"] for i in reversed(items)]
    assert (
        client.put(f"/api/playlists/{pid}/order", json={"item_ids": [items[0]["id"]]}).status_code
        == 400
    )
    assert client.delete(f"/api/playlists/{pid}/items/{items[-1]['id']}").status_code == 204
    assert client.get(f"/api/playlists/{pid}").json()["item_count"] == 3

    # Refresh from the filter: a new matching tag appears, the note survives, extras go.
    client.post("/api/auth/logout")
    login(client, analyst.email)
    new_tag = client.post(
        f"/api/events/{data['m2']['id']}/tags",
        json={
            "code": "Lineout",
            "start_ms": 9000,
            "end_ms": 12000,
            "descriptors": {"outcome": "Lost"},
        },
    ).json()
    client.post("/api/auth/logout")
    login(client, coach.email)
    refreshed = client.post(f"/api/playlists/{pid}/refresh").json()
    assert [i["tag_id"] for i in refreshed["items"]] == [
        data["tags"]["c"]["id"],
        new_tag["id"],
        data["tags"]["a"]["id"],
    ]
    assert refreshed["items"][0]["note"] == "Overthrown at the back"

    # Rename, duplicate, delete.
    assert (
        client.patch(f"/api/playlists/{pid}", json={"name": "Lineouts we lost"}).json()["name"]
        == "Lineouts we lost"
    )
    copy = client.post(f"/api/playlists/{pid}/duplicate").json()
    assert (
        copy["name"] == "Lineouts we lost (copy)" and copy["item_count"] == 3 and copy["id"] != pid
    )
    assert len(client.get(f"/api/squads/{sid}/playlists").json()) == 2
    assert client.delete(f"/api/playlists/{copy['id']}").status_code == 204
    assert client.post(f"/api/playlists/{copy['id']}/refresh").status_code == 404

    plain = client.post(
        f"/api/squads/{sid}/playlists",
        json={"name": "Hand picked", "tag_ids": [data["tags"]["d"]["id"]]},
    ).json()
    assert plain["item_count"] == 1
    assert client.post(f"/api/playlists/{plain['id']}/refresh").status_code == 400


def test_sharing_and_permissions(
    client: ApiClient,
    db: Session,
    squad: Squad,
    analyst: User,
    coach: User,
    outsider: User,
    admin: User,
) -> None:
    login(client, analyst.email)
    data = _seed(client, squad)
    client.post("/api/auth/logout")
    other_coach = make_user(db, email="coach2@example.com")
    add_member(db, other_coach, squad, Role.COACH)

    login(client, coach.email)
    sid = str(squad.id)
    playlist = client.post(
        f"/api/squads/{sid}/playlists",
        json={"name": "Private", "tag_ids": [data["tags"]["a"]["id"]]},
    ).json()
    pid = playlist["id"]
    bad_share = client.put(f"/api/playlists/{pid}/shares", json={"user_ids": [str(outsider.id)]})
    assert bad_share.status_code == 400
    shared = client.put(f"/api/playlists/{pid}/shares", json={"user_ids": [str(analyst.id)]}).json()
    assert [s["name"] for s in shared["shared_with"]] == [analyst.name]
    client.post("/api/auth/logout")

    # Shared with the analyst: can view and duplicate, cannot change.
    login(client, analyst.email)
    assert [p["id"] for p in client.get(f"/api/squads/{sid}/playlists").json()] == [pid]
    view = client.get(f"/api/playlists/{pid}").json()
    assert view["can_edit"] is False
    assert client.patch(f"/api/playlists/{pid}", json={"name": "x"}).status_code == 403
    assert (
        client.post(
            f"/api/playlists/{pid}/items", json={"tag_ids": [data["tags"]["b"]["id"]]}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/playlists/{pid}").status_code == 403
    assert client.post(f"/api/playlists/{pid}/duplicate").status_code == 201
    client.post("/api/auth/logout")

    # Not shared with the other coach: it does not exist for them.
    login(client, "coach2@example.com")
    assert client.get(f"/api/squads/{sid}/playlists").json() == []
    assert client.get(f"/api/playlists/{pid}").status_code == 404
    assert client.patch(f"/api/playlists/{pid}", json={"name": "x"}).status_code == 404
    client.post("/api/auth/logout")

    # Outsiders see nothing; the squad admin (superadmin here) sees and can edit everything.
    login(client, outsider.email)
    assert client.get(f"/api/squads/{sid}/playlists").status_code == 404
    assert client.get(f"/api/playlists/{pid}").status_code == 404
    client.post("/api/auth/logout")

    login(client, admin.email)
    names = sorted(p["name"] for p in client.get(f"/api/squads/{sid}/playlists").json())
    assert names == ["Private", "Private (copy)"]
    assert (
        client.patch(f"/api/playlists/{pid}", json={"name": "Renamed by admin"}).status_code == 200
    )

    # Tags from another squad cannot be added.
    client.post("/api/auth/logout")
    login(client, coach.email)
    foreign = client.post(
        f"/api/playlists/{pid}/items",
        json={
            "tag_ids": [data["tags"]["a"]["id"]],
            "ranges": [{"event_id": str(squad.id), "start_ms": 0, "end_ms": 10}],
        },
    )
    assert foreign.status_code == 400
