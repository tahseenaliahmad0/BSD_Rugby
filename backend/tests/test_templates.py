from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.models import Squad, User
from app.schemas.templates import RESERVED_HOTKEYS
from app.services.default_templates import default_templates
from tests.conftest import ApiClient, login


def _minimal(**overrides: Any) -> dict[str, Any]:
    content: dict[str, Any] = {
        "name": "Test template",
        "buttons": [
            {
                "code": "Scrum",
                "hotkey": "2",
                "colour": "#e8590c",
                "kind": "span",
                "groups": ["outcome"],
            },
            {"code": "Tackle", "hotkey": "t", "lead_ms": 3000, "lag_ms": 2000},
        ],
        "descriptor_groups": [
            {
                "key": "outcome",
                "label": "Outcome",
                "options": [{"value": "Won", "hotkey": "A"}, {"value": "Lost"}],
            }
        ],
        "outcome_group": "outcome",
        "success_values": ["Won"],
    }
    content.update(overrides)
    return content


def test_default_templates_are_valid_and_avoid_player_keys() -> None:
    for template in default_templates():
        keys = [b.hotkey for b in template.buttons if b.hotkey]
        keys += [o.hotkey for g in template.descriptor_groups for o in g.options if o.hotkey]
        assert len(keys) == len(set(keys)), template.name
        assert not set(keys) & RESERVED_HOTKEYS
        assert template.outcome_group == "outcome"
        assert {b.kind for b in template.buttons} == {"instant", "span"}


def test_new_squad_gets_default_templates(client: ApiClient, admin: User) -> None:
    login(client, admin.email)
    squad = client.post("/api/squads", json={"name": "Women's 1st XV"}).json()
    templates = client.get(f"/api/squads/{squad['id']}/templates").json()
    assert [t["name"] for t in templates] == ["Rugby sevens", "Rugby union 15s"]
    assert all(t["version"] == 1 and t["is_active"] for t in templates)
    fifteens = next(t for t in templates if t["name"] == "Rugby union 15s")
    assert len(fifteens["buttons"]) == 14
    assert fifteens["success_values"] == ["Won"]
    # Calling defaults again does not duplicate them.
    again = client.post(f"/api/squads/{squad['id']}/templates/defaults").json()
    assert len(again) == 2


def test_permissions(
    client: ApiClient, squad: Squad, analyst: User, coach: User, outsider: User
) -> None:
    login(client, analyst.email)
    created = client.post(f"/api/squads/{squad.id}/templates", json=_minimal())
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]
    client.post("/api/auth/logout")

    login(client, coach.email)
    assert client.get(f"/api/squads/{squad.id}/templates").status_code == 200
    assert client.get(f"/api/templates/{template_id}").status_code == 200
    assert client.post(f"/api/squads/{squad.id}/templates", json=_minimal()).status_code == 403
    assert client.put(f"/api/templates/{template_id}", json=_minimal()).status_code == 403
    assert client.delete(f"/api/templates/{template_id}").status_code == 403
    client.post("/api/auth/logout")

    login(client, outsider.email)
    assert client.get(f"/api/squads/{squad.id}/templates").status_code == 404
    assert client.get(f"/api/templates/{template_id}").status_code == 404
    assert client.put(f"/api/templates/{template_id}", json=_minimal()).status_code == 404


def test_editing_creates_a_new_version_and_keeps_the_old_one(
    client: ApiClient, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    v1 = client.post(f"/api/squads/{squad.id}/templates", json=_minimal()).json()
    edited = _minimal(name="Renamed")
    edited["buttons"].append({"code": "Try", "hotkey": "y", "colour": "#d6336c"})
    v2 = client.put(f"/api/templates/{v1['id']}", json=edited).json()
    assert v2["family_id"] == v1["family_id"]
    assert v2["version"] == 2 and v2["is_active"]
    assert v2["name"] == "Renamed" and len(v2["buttons"]) == 3

    old = client.get(f"/api/templates/{v1['id']}").json()
    assert old["version"] == 1 and not old["is_active"] and len(old["buttons"]) == 2

    active = client.get(f"/api/squads/{squad.id}/templates").json()
    assert [t["id"] for t in active] == [v2["id"]]
    versions = client.get(f"/api/templates/{v2['id']}/versions").json()
    assert [(v["version"], v["is_active"]) for v in versions] == [(2, True), (1, False)]

    # Roll back to version 1.
    assert client.post(f"/api/templates/{v1['id']}/activate").json()["is_active"]
    assert client.get(f"/api/templates/{v2['id']}").json()["is_active"] is False

    # Editing an old version branches from it but still numbers after the latest.
    v3 = client.put(f"/api/templates/{v1['id']}", json=_minimal(name="From v1")).json()
    assert v3["version"] == 3 and v3["is_active"]


def test_validation_rejects_clashes_reserved_keys_and_bad_groups(
    client: ApiClient, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    url = f"/api/squads/{squad.id}/templates"

    clash = _minimal()
    clash["buttons"][1]["hotkey"] = "2"
    response = client.post(url, json=clash)
    assert response.status_code == 422
    assert "'2' is used by Scrum, Tackle" in response.text

    reserved = _minimal()
    reserved["buttons"][1]["hotkey"] = "k"
    response = client.post(url, json=reserved)
    assert response.status_code == 422 and "video player" in response.text

    unknown_group = _minimal()
    unknown_group["buttons"][0]["groups"] = ["zone"]
    assert "unknown group" in client.post(url, json=unknown_group).text

    bad_success = _minimal(success_values=["Drawn"])
    assert "Success values" in client.post(url, json=bad_success).text

    duplicate_code = _minimal()
    duplicate_code["buttons"][1]["code"] = "scrum"
    assert "Duplicate codes" in client.post(url, json=duplicate_code).text

    # The validate endpoint reports the same problems without saving.
    check = client.post(f"{url}/validate", json=clash).json()
    assert check["ok"] is False and any("'2'" in e for e in check["errors"])
    ok = client.post(f"{url}/validate", json=_minimal()).json()
    assert ok == {"ok": True, "errors": [], "clashes": []}
    assert client.get(url).json() == []


def test_retire_family(client: ApiClient, db: Session, squad: Squad, admin: User) -> None:
    login(client, admin.email)
    created = client.post(f"/api/squads/{squad.id}/templates", json=_minimal()).json()
    assert client.delete(f"/api/templates/{created['id']}").status_code == 204
    assert client.get(f"/api/squads/{squad.id}/templates").json() == []
    kept = client.get(f"/api/templates/{created['id']}").json()
    assert cast(dict[str, Any], kept)["is_active"] is False
