"""Upload a clip over tus, have it transcoded (inline), then fetch it with access control."""

from __future__ import annotations

import base64
import itertools
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job, Squad, User, Video
from app.services.ffmpeg import generate_test_clip
from tests.conftest import ApiClient, login, make_user

TUS = {"Tus-Resumable": "1.0.0"}


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("clip") / "match test.mp4"
    generate_test_clip(path, get_settings(), duration_s=3.0, fps=30, size="320x240")
    return path


def _metadata(**pairs: str) -> str:
    return ",".join(f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in pairs.items())


def _create_match(client: ApiClient, squad_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/squads/{squad_id}/events", json={"date": "2026-10-03", "opponent_name": "Yale"}
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _tus_upload(client: ApiClient, event_id: str, clip: Path, chunk: int) -> str:
    data = clip.read_bytes()
    created = client.post(
        "/api/uploads",
        headers={
            **TUS,
            "Upload-Length": str(len(data)),
            "Upload-Metadata": _metadata(filename=clip.name, eventId=event_id, cameraLabel="Main"),
        },
    )
    assert created.status_code == 201, created.text
    location: str = created.headers["Location"]
    assert location.startswith("/api/uploads/")
    offset = 0
    while offset < len(data):
        piece = data[offset : offset + chunk]
        patched = client.patch(
            location,
            content=piece,
            headers={
                **TUS,
                "Content-Type": "application/offset+octet-stream",
                "Upload-Offset": str(offset),
            },
        )
        assert patched.status_code == 204, patched.text
        offset = int(patched.headers["Upload-Offset"])
        head = client.head(location, headers=TUS)
        assert head.status_code == 200
        assert head.headers["Upload-Offset"] == str(offset)
    return location.rsplit("/", 1)[1]


def _keyframe_times(path: Path) -> list[float]:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-skip_frame",
            "nokey",
            "-show_entries",
            "frame=pts_time",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [float(f["pts_time"]) for f in json.loads(out)["frames"]]


def test_upload_creates_video_and_transcodes(
    client: ApiClient, db: Session, squad: Squad, analyst: User, clip: Path, storage_root: Path
) -> None:
    login(client, analyst.email)
    match = _create_match(client, str(squad.id))

    upload_id = _tus_upload(client, match["id"], clip, chunk=200_000)
    status = client.get(f"/api/uploads/{upload_id}").json()
    assert status["status"] == "completed"
    assert status["video_id"]

    video = client.get(f"/api/videos/{status['video_id']}").json()
    assert video["status"] == "ready", video
    assert video["fps_num"] == 30 and video["fps_den"] == 1
    assert video["fps"] == 30.0
    assert 2.9 <= video["duration_s"] <= 3.2
    assert video["frame_count"] == 90
    assert video["width"] == 320 and video["height"] == 240
    assert video["proxy_url"] == f"/media/proxies/{video['id']}/proxy.mp4"
    assert video["poster_url"] == f"/media/proxies/{video['id']}/poster.jpg"
    assert video["thumbnail_url_template"].endswith("/thumbs/{index}.jpg")
    assert video["thumbnail_count"] == 2  # 3 s clip, one thumbnail every 2 s in tests
    assert video["original_filename"] == "match test.mp4"

    # The original is untouched and lives in its own folder.
    row = db.get(Video, video["id"])
    assert row is not None
    original = storage_root / row.original_path
    assert original.read_bytes() == clip.read_bytes()
    assert original.parent.name == video["id"]
    assert not list((storage_root / "uploads").glob("*.part"))

    # The proxy is H.264/AAC with faststart (moov before mdat) and a keyframe every second.
    proxy = storage_root / "proxies" / video["id"] / "proxy.mp4"
    head = proxy.read_bytes()[: 1024 * 1024]
    assert head.find(b"moov") < head.find(b"mdat")
    probe = json.loads(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(proxy)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    codecs = {s["codec_type"]: s["codec_name"] for s in probe["streams"]}
    assert codecs == {"video": "h264", "audio": "aac"}
    times = _keyframe_times(proxy)
    assert times[0] == 0.0
    assert all(b - a <= 1.0 + 1e-6 for a, b in itertools.pairwise(times))
    assert (storage_root / "proxies" / video["id"] / "thumbs" / "thumbs.vtt").exists()

    # The job reports success with full progress and a log.
    jobs = client.get(f"/api/videos/{video['id']}/jobs").json()
    assert len(jobs) == 1
    job = client.get(f"/api/jobs/{jobs[0]['id']}").json()
    assert job["status"] == "succeeded"
    assert job["progress"] == 1.0
    assert job["type"] == "transcode" and job["queue"] == "cpu"
    assert job["output"]["encoder"] == "libx264"
    assert "probe:" in job["log"]
    squad_jobs = client.get(f"/api/squads/{squad.id}/jobs").json()
    assert [j["id"] for j in squad_jobs] == [job["id"]]

    # The match now lists the video.
    event = client.get(f"/api/events/{match['id']}").json()
    assert event["video_count"] == 1
    assert event["videos"][0]["id"] == video["id"]


def test_upload_permissions_and_protocol_errors(
    client: ApiClient, squad: Squad, analyst: User, coach: User, outsider: User, clip: Path
) -> None:
    login(client, analyst.email)
    match = _create_match(client, str(squad.id))
    client.post("/api/auth/logout")

    # Coaches can watch but not upload; outsiders do not learn the match exists.
    for user, expected in ((coach, 403), (outsider, 404)):
        login(client, user.email)
        response = client.post(
            "/api/uploads",
            headers={
                **TUS,
                "Upload-Length": "10",
                "Upload-Metadata": _metadata(eventId=match["id"]),
            },
        )
        assert response.status_code == expected
        client.post("/api/auth/logout")

    login(client, analyst.email)
    assert (
        client.options("/api/uploads").headers["Tus-Extension"] == "creation,termination,expiration"
    )
    missing_length = client.post(
        "/api/uploads", headers={**TUS, "Upload-Metadata": _metadata(eventId=match["id"])}
    )
    assert missing_length.status_code == 400
    no_event = client.post("/api/uploads", headers={**TUS, "Upload-Length": "10"})
    assert no_event.status_code == 400

    created = client.post(
        "/api/uploads",
        headers={
            **TUS,
            "Upload-Length": "10",
            "Upload-Metadata": _metadata(eventId=match["id"], filename="a.mp4"),
        },
    )
    location: str = created.headers["Location"]
    wrong_type = client.patch(location, content=b"12345", headers={**TUS, "Upload-Offset": "0"})
    assert wrong_type.status_code == 415
    ok = client.patch(
        location,
        content=b"12345",
        headers={**TUS, "Upload-Offset": "0", "Content-Type": "application/offset+octet-stream"},
    )
    assert ok.status_code == 204 and ok.headers["Upload-Offset"] == "5"
    wrong_offset = client.patch(
        location,
        content=b"12345",
        headers={**TUS, "Upload-Offset": "3", "Content-Type": "application/offset+octet-stream"},
    )
    assert wrong_offset.status_code == 409
    too_much = client.patch(
        location,
        content=b"123456789",
        headers={**TUS, "Upload-Offset": "5", "Content-Type": "application/offset+octet-stream"},
    )
    assert too_much.status_code == 400

    # Only the uploader (or a superadmin) can see or resume an upload.
    client.post("/api/auth/logout")
    login(client, coach.email)
    assert client.head(location, headers=TUS).status_code == 404
    client.post("/api/auth/logout")

    login(client, analyst.email)
    assert client.delete(location, headers=TUS).status_code == 204
    assert client.head(location, headers=TUS).status_code == 404


def test_media_access_control(
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
    match = _create_match(client, str(squad.id))
    upload_id = _tus_upload(client, match["id"], clip, chunk=10_000_000)
    video_id = client.get(f"/api/uploads/{upload_id}").json()["video_id"]
    proxy_url = f"/media/proxies/{video_id}/proxy.mp4"
    client.post("/api/auth/logout")

    # Anonymous: 401 from both the dev file route and the Caddy authorize endpoint.
    assert client.get(proxy_url).status_code == 401
    assert (
        client.get("/api/media/authorize", headers={"X-Forwarded-Uri": proxy_url}).status_code
        == 401
    )

    # A coach in the squad can stream it, with byte ranges.
    login(client, coach.email)
    full = client.get(proxy_url)
    assert full.status_code == 200
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["accept-ranges"] == "bytes"
    partial = client.get(proxy_url, headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert len(partial.content) == 100
    assert partial.headers["content-range"].startswith("bytes 0-99/")
    assert (
        client.get(f"/media/proxies/{video_id}/poster.jpg").headers["content-type"] == "image/jpeg"
    )
    assert client.get(f"/media/proxies/{video_id}/thumbs/00001.jpg").status_code == 200
    assert (
        client.get(f"/media/proxies/{video_id}/thumbs/thumbs.vtt")
        .headers["content-type"]
        .startswith("text/vtt")
    )
    assert client.get(f"/media/originals/{video_id}/match%20test.mp4").status_code == 200
    for uri in (proxy_url, f"/media/originals/{video_id}/match%20test.mp4"):
        assert (
            client.get("/api/media/authorize", headers={"X-Forwarded-Uri": uri}).status_code == 204
        )
    # Caddy may strip the /media prefix before asking; both forms are accepted.
    assert (
        client.get(
            "/api/media/authorize", headers={"X-Forwarded-Uri": f"/proxies/{video_id}/proxy.mp4"}
        ).status_code
        == 204
    )
    # The in-progress uploads folder and anything outside the layout are never served.
    for uri in ("/media/uploads/x.part", "/uploads/x.part", "proxies/x", ""):
        assert client.get("/api/media/authorize", headers={"X-Forwarded-Uri": uri}).status_code in (
            400,
            404,
        ), uri
    assert (
        client.get(
            "/api/media/authorize",
            headers={"X-Forwarded-Uri": f"/media/proxies/{video_id}/../../x"},
        ).status_code
        == 404
    )
    assert client.get(f"/media/proxies/{video_id}/missing.jpg").status_code == 404
    client.post("/api/auth/logout")

    # A member of another squad gets 404 everywhere.
    login(client, outsider.email)
    assert client.get(proxy_url).status_code == 404
    assert (
        client.get("/api/media/authorize", headers={"X-Forwarded-Uri": proxy_url}).status_code
        == 404
    )
    assert client.get(f"/api/videos/{video_id}").status_code == 404

    # An admin can delete the video, which removes its files and jobs.
    client.post("/api/auth/logout")
    login(client, analyst.email)
    assert client.delete(f"/api/videos/{video_id}").status_code == 403
    client.post("/api/auth/logout")
    admin_user = make_user(db, email="boss@example.com", superadmin=True)
    login(client, admin_user.email)
    assert client.delete(f"/api/videos/{video_id}").status_code == 204
    assert not (storage_root / "proxies" / video_id).exists()
    assert not (storage_root / "originals" / video_id).exists()
    assert db.query(Job).count() == 0


def test_celery_routes_transcode_to_cpu_queue() -> None:
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert routes["app.workers.tasks.transcode_video"]["queue"] == "cpu"
    assert routes["app.workers.tasks.gpu_ping"]["queue"] == "gpu"
    assert {q.name for q in celery_app.conf.task_queues} == {"cpu", "gpu"}
