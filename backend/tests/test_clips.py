"""Clip search across matches with the JSONB filter builder, and saved filters."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import Event, Player, Squad, Tag, User
from app.schemas.clips import FilterDefinition
from app.services.clips import apply_filter
from tests.conftest import ApiClient, login, make_squad


def _setup(client: ApiClient, db: Session, squad: Squad) -> dict[str, Any]:
    season_a = client.post(f"/api/squads/{squad.id}/seasons", json={"name": "2025-26"}).json()
    season_b = client.post(f"/api/squads/{squad.id}/seasons", json={"name": "2026-27"}).json()
    yale = client.post(
        f"/api/squads/{squad.id}/events",
        json={"date": "2026-10-03", "opponent_name": "Yale", "season_id": season_b["id"]},
    ).json()
    harvard = client.post(
        f"/api/squads/{squad.id}/events",
        json={"date": "2025-11-01", "opponent_name": "Harvard", "season_id": season_a["id"]},
    ).json()
    training = client.post(
        f"/api/squads/{squad.id}/events",
        json={
            "date": "2026-10-05",
            "type": "training",
            "title": "Lineouts",
            "season_id": season_b["id"],
        },
    ).json()
    p10 = Player(squad_id=squad.id, name="Fly Half", shirt_number=10)
    p7 = Player(squad_id=squad.id, name="Flanker", shirt_number=7)
    db.add_all([p10, p7])
    db.commit()

    def tag(event: dict[str, Any], code: str, start: int, **extra: Any) -> dict[str, Any]:
        body = {"code": code, "start_ms": start, "end_ms": start + 5000, **extra}
        r = client.post(f"/api/events/{event['id']}/tags", json=body)
        assert r.status_code == 201, r.text
        return dict(r.json())

    tags = {
        "yale_lineout_lost_22": tag(
            yale, "Lineout", 1000, descriptors={"outcome": "Lost", "zone": "Opp 22"}
        ),
        "yale_lineout_won": tag(
            yale, "Lineout", 9000, descriptors={"outcome": "Won", "zone": "Own half"}
        ),
        "yale_scrum_lost": tag(
            yale,
            "Scrum",
            20000,
            descriptors={"outcome": "Lost", "zone": "Opp 22"},
            player_ids=[str(p7.id)],
        ),
        "harvard_lineout_lost": tag(
            harvard,
            "Lineout",
            3000,
            descriptors={"outcome": "Lost", "zone": "Opp 22"},
            note="Overthrown",
        ),
        "harvard_carry_10": tag(
            harvard,
            "Carry",
            7000,
            descriptors={"zone": ["Opp half", "Opp 22"]},
            player_ids=[str(p10.id)],
        ),
        "training_lineout": tag(training, "Lineout", 500, descriptors={"outcome": "Won"}),
    }
    return {
        "season_a": season_a,
        "season_b": season_b,
        "yale": yale,
        "harvard": harvard,
        "training": training,
        "p10": p10,
        "p7": p7,
        "tags": tags,
    }


def _ids(client: ApiClient, squad_id: str, flt: dict[str, Any], **extra: Any) -> list[str]:
    r = client.post(f"/api/squads/{squad_id}/clips/search", json={"filter": flt, **extra})
    assert r.status_code == 200, r.text
    return [c["tag"]["id"] for c in r.json()["clips"]]


def test_filters_combine_with_and_across_fields_and_or_within(
    client: ApiClient, db: Session, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    data = _setup(client, db, squad)
    t = data["tags"]
    sid = str(squad.id)

    everything = client.post(f"/api/squads/{sid}/clips/search", json={}).json()
    assert everything["total"] == 6
    # Most recent match first, then by start time.
    assert [c["tag"]["id"] for c in everything["clips"]][:3] == [
        t["training_lineout"]["id"],
        t["yale_lineout_lost_22"]["id"],
        t["yale_lineout_won"]["id"],
    ]

    lineouts = set(_ids(client, sid, {"codes": ["Lineout"]}))
    assert lineouts == {
        t["yale_lineout_lost_22"]["id"],
        t["yale_lineout_won"]["id"],
        t["harvard_lineout_lost"]["id"],
        t["training_lineout"]["id"],
    }

    lost_lineouts_in_22 = set(
        _ids(
            client,
            sid,
            {"codes": ["Lineout"], "descriptors": {"outcome": ["Lost"], "zone": ["Opp 22"]}},
        )
    )
    assert lost_lineouts_in_22 == {t["yale_lineout_lost_22"]["id"], t["harvard_lineout_lost"]["id"]}

    # OR within a field: Lineout or Scrum, zone Opp 22 or Own half.
    either = set(
        _ids(
            client,
            sid,
            {"codes": ["Lineout", "Scrum"], "descriptors": {"zone": ["Opp 22", "Own half"]}},
        )
    )
    assert either == {
        t["yale_lineout_lost_22"]["id"],
        t["yale_lineout_won"]["id"],
        t["yale_scrum_lost"]["id"],
        t["harvard_lineout_lost"]["id"],
    }

    # Multi-valued descriptors (stored as a list) match any of their values.
    assert _ids(client, sid, {"codes": ["Carry"], "descriptors": {"zone": ["Opp 22"]}}) == [
        t["harvard_carry_10"]["id"]
    ]
    assert _ids(client, sid, {"descriptors": {"zone": ["Own 22"]}}) == []

    # Players, events, seasons, opponents, type, dates, note text.
    assert _ids(client, sid, {"player_ids": [str(data["p10"].id)]}) == [t["harvard_carry_10"]["id"]]
    assert set(_ids(client, sid, {"player_ids": [str(data["p10"].id), str(data["p7"].id)]})) == {
        t["harvard_carry_10"]["id"],
        t["yale_scrum_lost"]["id"],
    }
    assert len(_ids(client, sid, {"event_ids": [data["yale"]["id"]]})) == 3
    assert len(_ids(client, sid, {"season_ids": [data["season_a"]["id"]]})) == 2
    assert len(_ids(client, sid, {"opponent_ids": [data["yale"]["opponent_id"]]})) == 3
    assert _ids(client, sid, {"event_types": ["training"]}) == [t["training_lineout"]["id"]]
    assert len(_ids(client, sid, {"date_from": "2026-01-01"})) == 4
    assert _ids(client, sid, {"text": "overthrown"}) == [t["harvard_lineout_lost"]["id"]]

    # Pagination.
    page = client.post(
        f"/api/squads/{sid}/clips/search", json={"filter": {}, "limit": 2, "offset": 4}
    ).json()
    assert page["total"] == 6 and len(page["clips"]) == 2

    # Clip payload: event and video details, video-relative times.
    clip = client.post(
        f"/api/squads/{sid}/clips/search", json={"filter": {"codes": ["Scrum"]}}
    ).json()["clips"][0]
    assert clip["event"]["display_title"] == "vs Yale" and clip["code"] == "Scrum"
    assert clip["video"] is None and clip["start_s"] is None  # no video uploaded yet
    assert clip["start_ms"] == 20000 and clip["end_ms"] == 25000


def test_descriptor_conditions_use_jsonb_containment() -> None:
    query = apply_filter(
        select(Tag).join(Event, Tag.event_id == Event.id),
        uuid.uuid4(),
        FilterDefinition(descriptors={"outcome": ["Lost"]}, codes=["Lineout"]),
    )
    sql = str(query.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    assert sql.count("@>") == 2  # scalar and list shapes of the same value
    assert "tags.code IN" in sql


def test_search_is_scoped_to_the_squad(
    client: ApiClient, db: Session, squad: Squad, analyst: User, outsider: User
) -> None:
    login(client, analyst.email)
    _setup(client, db, squad)
    client.post("/api/auth/logout")

    login(client, outsider.email)
    other = client.get("/api/squads").json()[0]
    assert client.post(f"/api/squads/{squad.id}/clips/search", json={}).status_code == 404
    assert client.post(f"/api/squads/{other['id']}/clips/search", json={}).json()["total"] == 0


def test_saved_filters_private_and_shared(
    client: ApiClient, db: Session, squad: Squad, analyst: User, coach: User
) -> None:
    login(client, coach.email)
    sid = str(squad.id)
    mine = client.post(
        f"/api/squads/{sid}/filters",
        json={
            "name": "Lost lineouts",
            "definition": {"codes": ["Lineout"], "descriptors": {"outcome": ["Lost"]}},
        },
    )
    assert mine.status_code == 201, mine.text
    shared = client.post(
        f"/api/squads/{sid}/filters",
        json={
            "name": "Opp 22",
            "definition": {"descriptors": {"zone": ["Opp 22"]}},
            "is_shared": True,
        },
    ).json()
    assert [f["name"] for f in client.get(f"/api/squads/{sid}/filters").json()] == [
        "Lost lineouts",
        "Opp 22",
    ]
    client.post("/api/auth/logout")

    login(client, analyst.email)
    visible = client.get(f"/api/squads/{sid}/filters").json()
    assert [f["name"] for f in visible] == ["Opp 22"]
    assert visible[0]["owner_name"] == coach.name
    assert client.get(f"/api/filters/{mine.json()['id']}").status_code == 404
    assert client.patch(f"/api/filters/{shared['id']}", json={"name": "x"}).status_code == 403
    assert client.delete(f"/api/filters/{shared['id']}").status_code == 403
    client.post("/api/auth/logout")

    login(client, coach.email)
    renamed = client.patch(
        f"/api/filters/{shared['id']}", json={"name": "Their 22", "is_shared": False}
    )
    assert renamed.json()["name"] == "Their 22" and renamed.json()["is_shared"] is False
    assert client.delete(f"/api/filters/{shared['id']}").status_code == 204
    assert len(client.get(f"/api/squads/{sid}/filters").json()) == 1

    # Another squad's filters are invisible.
    other = make_squad(db, "Other")
    assert client.get(f"/api/squads/{other.id}/filters").status_code == 404
