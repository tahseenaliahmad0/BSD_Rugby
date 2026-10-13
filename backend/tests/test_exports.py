"""Exports: a clip or a playlist rendered to MP4 by the worker, listed, downloaded and deleted."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Squad, User
from app.services.export_render import find_font
from app.services.ffmpeg import generate_test_clip
from tests.conftest import ApiClient, login
from tests.test_uploads import _tus_upload


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("clip") / "export source.mp4"
    generate_test_clip(path, get_settings(), duration_s=6.0, fps=25, size="320x240")
    return path


def _probe(path: Path) -> dict[str, Any]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return dict(json.loads(out))


def _match_with_video(client: ApiClient, squad: Squad, clip: Path) -> dict[str, Any]:
    match = client.post(
        f"/api/squads/{squad.id}/events", json={"date": "2026-10-03", "opponent_name": "Yale"}
    ).json()
    upload_id = _tus_upload(client, match["id"], clip, chunk=10_000_000)
    video_id = client.get(f"/api/uploads/{upload_id}").json()["video_id"]
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "ready"
    return dict(match)


def test_clip_and_playlist_exports(
    client: ApiClient,
    db: Session,
    squad: Squad,
    analyst: User,
    coach: User,
    outsider: User,
    clip: Path,
    storage_root: Path,
) -> None:
    login(client, analyst.email)
    match = _match_with_video(client, squad, clip)
    t1 = client.post(
        f"/api/events/{match['id']}/tags",
        json={"code": "Lineout", "start_ms": 500, "end_ms": 2000, "note": "Overthrown"},
    ).json()
    t2 = client.post(
        f"/api/events/{match['id']}/tags", json={"code": "Scrum", "start_ms": 3000, "end_ms": 5500}
    ).json()
    client.post("/api/auth/logout")

    login(client, coach.email)
    sid = str(squad.id)
    created = client.post(
        f"/api/squads/{sid}/exports",
        json={"kind": "clip", "tag_id": t1["id"], "with_captions": True},
    )
    assert created.status_code == 202, created.text
    export = created.json()
    assert export["name"] == "Lineout - vs Yale" and export["clip_count"] == 1
    # The task ran inline (eager Celery), so it is already finished.
    done = client.get(f"/api/exports/{export['id']}").json()
    assert done["status"] == "succeeded", done
    assert done["progress"] == 1.0 and done["file_url"].startswith(
        f"/media/exports/{export['id']}/"
    )
    file_path = storage_root / done["file_url"].removeprefix("/media/")
    assert file_path.exists() and done["size_bytes"] == file_path.stat().st_size
    probe = _probe(file_path)
    assert abs(float(probe["format"]["duration"]) - 1.5) < 0.2
    codecs = {s["codec_type"]: s["codec_name"] for s in probe["streams"]}
    assert codecs == {"video": "h264", "audio": "aac"}
    video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video_stream["width"], video_stream["height"]) == (1280, 720)
    assert find_font() is not None, "captions need a font; install fonts-dejavu-core"

    # Download through the media route with access control.
    assert client.get(done["file_url"]).status_code == 200
    assert client.get(done["file_url"], headers={"Range": "bytes=0-10"}).status_code == 206
    assert (
        client.get(
            "/api/media/authorize", headers={"X-Forwarded-Uri": done["file_url"]}
        ).status_code
        == 204
    )

    # Playlist export joins the clips in order.
    playlist = client.post(
        f"/api/squads/{sid}/playlists", json={"name": "Set piece", "tag_ids": [t2["id"], t1["id"]]}
    ).json()
    pl_export = client.post(
        f"/api/squads/{sid}/exports", json={"kind": "playlist", "playlist_id": playlist["id"]}
    ).json()
    pl_done = client.get(f"/api/exports/{pl_export['id']}").json()
    assert pl_done["status"] == "succeeded", pl_done
    assert pl_done["name"] == "Set piece" and pl_done["clip_count"] == 2
    pl_probe = _probe(storage_root / pl_done["file_url"].removeprefix("/media/"))
    assert abs(float(pl_probe["format"]["duration"]) - 4.0) < 0.3

    # Ad-hoc range export.
    rng = client.post(
        f"/api/squads/{sid}/exports",
        json={
            "kind": "range",
            "range": {"event_id": match["id"], "start_ms": 0, "end_ms": 1000, "note": "Kick off"},
            "with_captions": False,
        },
    ).json()
    assert client.get(f"/api/exports/{rng['id']}").json()["status"] == "succeeded"

    listed = client.get(f"/api/squads/{sid}/exports").json()
    assert [e["kind"] for e in listed] == ["range", "playlist", "clip"]
    assert listed[0]["owner_name"] == coach.name

    # Only the owner or a squad admin deletes; outsiders see nothing.
    client.post("/api/auth/logout")
    login(client, analyst.email)
    assert client.delete(f"/api/exports/{export['id']}").status_code == 403
    client.post("/api/auth/logout")
    login(client, outsider.email)
    assert client.get(f"/api/exports/{export['id']}").status_code == 404
    assert client.get(done["file_url"]).status_code == 404
    assert client.get(f"/api/squads/{sid}/exports").status_code == 404
    client.post("/api/auth/logout")
    login(client, coach.email)
    assert client.delete(f"/api/exports/{export['id']}").status_code == 204
    assert not file_path.exists()
    assert client.get(f"/api/exports/{export['id']}").status_code == 404


def test_export_needs_a_video_and_a_valid_source(
    client: ApiClient, squad: Squad, analyst: User
) -> None:
    login(client, analyst.email)
    match = client.post(
        f"/api/squads/{squad.id}/events", json={"date": "2026-10-03", "opponent_name": "Yale"}
    ).json()
    tag = client.post(
        f"/api/events/{match['id']}/tags", json={"code": "Try", "start_ms": 0, "end_ms": 1000}
    ).json()
    no_video = client.post(
        f"/api/squads/{squad.id}/exports", json={"kind": "clip", "tag_id": tag["id"]}
    )
    assert no_video.status_code == 400 and "no video" in no_video.json()["detail"]
    missing = client.post(f"/api/squads/{squad.id}/exports", json={"kind": "playlist"})
    assert missing.status_code == 422
    assert client.get(f"/api/squads/{squad.id}/exports").json() == []
