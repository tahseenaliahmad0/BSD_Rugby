"""Stats: counts per code, success rates from the outcome group, per-player table, CSV."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Player, Squad, User
from tests.conftest import ApiClient, login


def _seed(client: ApiClient, db: Session, squad: Squad) -> dict[str, Any]:
    client.post(f"/api/squads/{squad.id}/templates/defaults")
    season = client.post(f"/api/squads/{squad.id}/seasons", json={"name": "2026-27"}).json()
    m1 = client.post(
        f"/api/squads/{squad.id}/events",
        json={"date": "2026-10-03", "opponent_name": "Yale", "season_id": season["id"]},
    ).json()
    m2 = client.post(
        f"/api/squads/{squad.id}/events",
        json={"date": "2026-10-10", "opponent_name": "Brown", "season_id": season["id"]},
    ).json()
    p9 = Player(squad_id=squad.id, name="Scrum Half", shirt_number=9)
    p2 = Player(squad_id=squad.id, name="Hooker", shirt_number=2)
    db.add_all([p9, p2])
    db.commit()

    def tag(event: dict[str, Any], code: str, start: int, **extra: Any) -> None:
        r = client.post(
            f"/api/events/{event['id']}/tags",
            json={"code": code, "start_ms": start, "end_ms": start + 1000, **extra},
        )
        assert r.status_code == 201, r.text

    tag(m1, "Lineout", 1000, descriptors={"outcome": "Won"}, player_ids=[str(p2.id)])
    tag(m1, "Lineout", 2000, descriptors={"outcome": "Lost"}, player_ids=[str(p2.id)])
    tag(m1, "Lineout", 3000, descriptors={"outcome": "Won"})
    tag(m1, "Scrum", 4000, descriptors={"outcome": "Lost"})
    tag(m1, "Carry", 5000, player_ids=[str(p9.id)])  # no outcome: counted, not rated
    tag(m2, "Lineout", 1000, descriptors={"outcome": "Lost"}, player_ids=[str(p2.id)])
    tag(m2, "Carry", 2000, player_ids=[str(p9.id), str(p2.id)])
    tag(
        m2,
        "Kick",
        3000,
        descriptors={"outcome": ["Won"], "kick_type": "Box"},
        player_ids=[str(p9.id)],
    )
    return {"season": season, "m1": m1, "m2": m2, "p9": p9, "p2": p2}


def test_per_match_and_per_season_stats(
    client: ApiClient, db: Session, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    data = _seed(client, db, squad)
    sid = str(squad.id)

    match = client.get(f"/api/squads/{sid}/stats", params={"event_id": data["m1"]["id"]}).json()
    assert match["template_name"] == "Rugby sevens" or match["template_name"] == "Rugby union 15s"
    assert match["outcome_group"] == "outcome" and match["success_values"] == ["Won"]
    assert match["tag_count"] == 5
    by_code = {row["code"]: row for row in match["codes"]}
    assert by_code["Lineout"]["count"] == 3
    assert by_code["Lineout"]["with_outcome"] == 3 and by_code["Lineout"]["successes"] == 2
    assert abs(by_code["Lineout"]["success_rate"] - 2 / 3) < 1e-9
    assert by_code["Scrum"]["success_rate"] == 0.0
    assert by_code["Carry"]["success_rate"] is None and by_code["Carry"]["count"] == 1
    # Codes come in template order.
    assert match["code_order"] == ["Scrum", "Lineout", "Carry"]
    # The row filters reproduce the clips.
    lost = by_code["Lineout"]["failure_filter"]
    found = client.post(f"/api/squads/{sid}/clips/search", json={"filter": lost}).json()
    assert found["total"] == 1 and found["clips"][0]["tag"]["descriptors"]["outcome"] == "Lost"
    assert lost["event_ids"] == [data["m1"]["id"]]

    season = client.get(
        f"/api/squads/{sid}/stats", params={"season_id": data["season"]["id"]}
    ).json()
    assert season["tag_count"] == 8
    by_code = {row["code"]: row for row in season["codes"]}
    assert by_code["Lineout"]["count"] == 4 and by_code["Lineout"]["successes"] == 2
    assert by_code["Kick"]["successes"] == 1  # list-valued outcome counts too
    players = {row["name"]: row for row in season["players"]}
    assert players["Hooker"]["shirt_number"] == 2
    assert players["Hooker"]["total"] == 4 and players["Hooker"]["by_code"] == {
        "Lineout": 3,
        "Carry": 1,
    }
    assert players["Hooker"]["successes"] == 1 and players["Hooker"]["with_outcome"] == 3
    assert players["Scrum Half"]["total"] == 3 and players["Scrum Half"]["success_rate"] == 1.0
    assert [r["name"] for r in season["players"]] == ["Hooker", "Scrum Half"]  # by shirt number
    player_clips = client.post(
        f"/api/squads/{sid}/clips/search", json={"filter": players["Hooker"]["filter"]}
    ).json()
    assert player_clips["total"] == 4

    everything = client.get(f"/api/squads/{sid}/stats").json()
    assert everything["tag_count"] == 8


def test_csv_export(
    client: ApiClient, db: Session, squad: Squad, coach: User, analyst: User
) -> None:
    login(client, analyst.email)
    data = _seed(client, db, squad)
    client.post("/api/auth/logout")
    login(client, coach.email)
    sid = str(squad.id)
    codes = client.get(
        f"/api/squads/{sid}/stats",
        params={"format": "csv", "table": "codes", "season_id": data["season"]["id"]},
    )
    assert codes.status_code == 200 and codes.headers["content-type"].startswith("text/csv")
    assert 'filename="stats-codes.csv"' in codes.headers["content-disposition"]
    lines = codes.text.strip().splitlines()
    assert lines[0] == "code,count,with_outcome,successes,success_rate"
    assert "Lineout,4,4,2,50.0%" in lines
    assert "Carry,2,0,0," in lines

    players = (
        client.get(f"/api/squads/{sid}/stats", params={"format": "csv", "table": "players"})
        .text.strip()
        .splitlines()
    )
    assert (
        players[0]
        == "player,shirt,total,Scrum,Lineout,Carry,Kick,with_outcome,successes,success_rate"
    )
    assert "Hooker,2,4,0,3,1,0,3,1,33.3%" in players
    assert "Scrum Half,9,3,0,0,2,1,1,1,100.0%" in players


def test_stats_without_template_or_outcome(
    client: ApiClient, db: Session, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    m = client.post(f"/api/squads/{squad.id}/events", json={"date": "2026-10-03"}).json()
    client.post(
        f"/api/events/{m['id']}/tags",
        json={"code": "Zebra", "start_ms": 0, "end_ms": 10, "descriptors": {"outcome": "Won"}},
    )
    stats = client.get(f"/api/squads/{squad.id}/stats").json()
    assert stats["template_name"] is None and stats["outcome_group"] is None
    assert stats["codes"][0]["code"] == "Zebra" and stats["codes"][0]["success_rate"] is None
    assert stats["codes"][0]["success_filter"] is None
