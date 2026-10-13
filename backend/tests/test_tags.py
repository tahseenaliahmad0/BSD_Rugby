"""Tags: creation, optimistic concurrency, split, merge, batch, permissions and scale."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import Player, Squad, User
from tests.conftest import ApiClient, login


def _match(client: ApiClient, squad_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/squads/{squad_id}/events", json={"date": "2026-10-03", "opponent_name": "Yale"}
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _tag(client: ApiClient, event_id: str, **fields: Any) -> dict[str, Any]:
    body = {"code": "Scrum", "start_ms": 10_000, "end_ms": 20_000, **fields}
    response = client.post(f"/api/events/{event_id}/tags", json=body)
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_create_list_and_permissions(
    client: ApiClient, db: Session, squad: Squad, analyst: User, coach: User, outsider: User
) -> None:
    player = Player(squad_id=squad.id, name="A. Back", shirt_number=10)
    db.add(player)
    db.commit()
    login(client, analyst.email)
    match = _match(client, str(squad.id))
    client.post(f"/api/squads/{squad.id}/templates/defaults")
    template = client.get(f"/api/squads/{squad.id}/templates").json()[1]
    tag = _tag(
        client,
        match["id"],
        template_id=template["id"],
        descriptors={"outcome": "Won", "zone": "Opp 22", "players_note": ""},
        player_ids=[str(player.id)],
        note="Good drive",
    )
    assert tag["version"] == 1
    assert tag["descriptors"] == {"outcome": "Won", "zone": "Opp 22"}  # empty values dropped
    assert tag["player_ids"] == [str(player.id)]
    assert tag["source"] == "manual" and tag["template_id"] == template["id"]

    bad = client.post(
        f"/api/events/{match['id']}/tags", json={"code": "Scrum", "start_ms": 5, "end_ms": 1}
    )
    assert bad.status_code == 422
    foreign = client.post(
        f"/api/events/{match['id']}/tags",
        json={"code": "Scrum", "start_ms": 1, "end_ms": 2, "player_ids": [str(uuid.uuid4())]},
    )
    assert foreign.status_code == 400 and "players" in foreign.json()["detail"]

    assert [t["id"] for t in client.get(f"/api/events/{match['id']}/tags").json()] == [tag["id"]]
    client.post("/api/auth/logout")

    login(client, coach.email)
    assert client.get(f"/api/events/{match['id']}/tags").status_code == 200
    assert client.get(f"/api/tags/{tag['id']}").status_code == 200
    assert (
        client.post(
            f"/api/events/{match['id']}/tags", json={"code": "x", "start_ms": 0, "end_ms": 1}
        ).status_code
        == 403
    )
    assert (
        client.patch(f"/api/tags/{tag['id']}", json={"version": 1, "note": "n"}).status_code == 403
    )
    assert client.delete(f"/api/tags/{tag['id']}").status_code == 403
    client.post("/api/auth/logout")

    login(client, outsider.email)
    assert client.get(f"/api/events/{match['id']}/tags").status_code == 404
    assert client.get(f"/api/tags/{tag['id']}").status_code == 404
    assert (
        client.patch(f"/api/tags/{tag['id']}", json={"version": 1, "note": "n"}).status_code == 404
    )


def test_optimistic_concurrency_conflict(client: ApiClient, squad: Squad, analyst: User) -> None:
    login(client, analyst.email)
    match = _match(client, str(squad.id))
    tag = _tag(client, match["id"])

    # First editor saves: version becomes 2.
    first = client.patch(f"/api/tags/{tag['id']}", json={"version": 1, "end_ms": 25_000})
    assert first.status_code == 200 and first.json()["version"] == 2

    # Second editor still holds version 1: clear conflict with the current tag in the body.
    second = client.patch(f"/api/tags/{tag['id']}", json={"version": 1, "end_ms": 30_000})
    assert second.status_code == 409
    body = second.json()
    assert "changed by someone else" in body["detail"]
    assert body["current"]["version"] == 2 and body["current"]["end_ms"] == 25_000
    assert client.get(f"/api/tags/{tag['id']}").json()["end_ms"] == 25_000  # not overwritten

    # Retrying with the current version succeeds.
    third = client.patch(f"/api/tags/{tag['id']}", json={"version": 2, "end_ms": 30_000})
    assert third.status_code == 200 and third.json()["version"] == 3

    # Deleting with a stale version is refused too; with the right one it works.
    assert client.delete(f"/api/tags/{tag['id']}", params={"version": 2}).status_code == 409
    assert client.delete(f"/api/tags/{tag['id']}", params={"version": 3}).status_code == 204
    gone = client.patch(f"/api/tags/{tag['id']}", json={"version": 3, "note": "late"})
    assert gone.status_code == 404


def test_split_merge_and_undo_by_recreating_ids(
    client: ApiClient, db: Session, squad: Squad, analyst: User
) -> None:
    player = Player(squad_id=squad.id, name="B. Prop", shirt_number=1)
    db.add(player)
    db.commit()
    login(client, analyst.email)
    match = _match(client, str(squad.id))
    tag = _tag(
        client, match["id"], descriptors={"outcome": "Won"}, player_ids=[str(player.id)], note="n1"
    )

    outside = client.post(f"/api/tags/{tag['id']}/split", json={"version": 1, "at_ms": 20_000})
    assert outside.status_code == 400
    split = client.post(f"/api/tags/{tag['id']}/split", json={"version": 1, "at_ms": 14_000})
    assert split.status_code == 200, split.text
    left, right = split.json()["left"], split.json()["right"]
    assert left["id"] == tag["id"] and (left["start_ms"], left["end_ms"]) == (10_000, 14_000)
    assert (right["start_ms"], right["end_ms"]) == (14_000, 20_000)
    assert right["descriptors"] == {"outcome": "Won"} and right["player_ids"] == [str(player.id)]
    assert left["version"] == 2 and right["version"] == 1
    stale_split = client.post(f"/api/tags/{tag['id']}/split", json={"version": 1, "at_ms": 12_000})
    assert stale_split.status_code == 409

    third = _tag(
        client,
        match["id"],
        start_ms=30_000,
        end_ms=40_000,
        descriptors={"zone": "Opp 22"},
        note="n3",
    )
    merged = client.post(
        f"/api/events/{match['id']}/tags/merge",
        json={"tags": [{"id": third["id"], "version": 1}, {"id": right["id"], "version": 1}]},
    )
    assert merged.status_code == 200, merged.text
    m = merged.json()
    assert m["id"] == right["id"]  # the earliest tag survives
    assert (m["start_ms"], m["end_ms"]) == (14_000, 40_000)
    assert m["descriptors"] == {"outcome": "Won", "zone": "Opp 22"}
    assert m["note"] == "n1 | n3" and m["player_ids"] == [str(player.id)]
    assert client.get(f"/api/tags/{third['id']}").status_code == 404
    stale_merge = client.post(
        f"/api/events/{match['id']}/tags/merge",
        json={"tags": [{"id": m["id"], "version": 1}, {"id": left["id"], "version": 2}]},
    )
    assert stale_merge.status_code == 409

    # Undo of the merge: delete the merged tag and re-create the originals with their ids.
    undo = client.post(
        f"/api/events/{match['id']}/tags/batch",
        json={
            "delete": [{"id": m["id"], "version": m["version"]}],
            "create": [
                {
                    **{
                        k: right[k]
                        for k in (
                            "id",
                            "code",
                            "start_ms",
                            "end_ms",
                            "descriptors",
                            "player_ids",
                            "note",
                        )
                    }
                },
                {
                    **{
                        k: third[k]
                        for k in (
                            "id",
                            "code",
                            "start_ms",
                            "end_ms",
                            "descriptors",
                            "player_ids",
                            "note",
                        )
                    }
                },
            ],
        },
    )
    assert undo.status_code == 200, undo.text
    assert undo.json()["deleted"] == [m["id"]]
    ids = {t["id"] for t in client.get(f"/api/events/{match['id']}/tags").json()}
    assert ids == {left["id"], right["id"], third["id"]}
    duplicate = client.post(
        f"/api/events/{match['id']}/tags",
        json={**{k: third[k] for k in ("id", "code", "start_ms", "end_ms")}},
    )
    assert duplicate.status_code == 400


def test_full_match_of_tags_is_fast(client: ApiClient, squad: Squad, analyst: User) -> None:
    login(client, analyst.email)
    match = _match(client, str(squad.id))
    codes = ["Ruck", "Carry", "Tackle", "Scrum", "Lineout", "Kick"]
    create = [
        {
            "code": codes[i % len(codes)],
            "start_ms": i * 3_200,
            "end_ms": i * 3_200 + 4_000,
            "descriptors": {"outcome": "Won" if i % 3 else "Lost", "zone": "Opp 22"},
        }
        for i in range(1_500)
    ]
    started = time.perf_counter()
    response = client.post(f"/api/events/{match['id']}/tags/batch", json={"create": create})
    assert response.status_code == 200, response.text[:300]
    assert len(response.json()["created"]) == 1_500
    created_in = time.perf_counter() - started

    started = time.perf_counter()
    tags = client.get(f"/api/events/{match['id']}/tags").json()
    listed_in = time.perf_counter() - started
    assert len(tags) == 1_500
    assert tags == sorted(tags, key=lambda t: t["start_ms"])
    assert listed_in < 2.0, f"listing 1,500 tags took {listed_in:.2f}s"
    assert created_in < 30.0, f"creating 1,500 tags took {created_in:.2f}s"
