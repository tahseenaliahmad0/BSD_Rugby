"""Resumable uploads: a tus 1.0.0 server (creation, termination, expiration extensions).

Flow: the browser POSTs to create an upload (Upload-Length and Upload-Metadata with the
filename, eventId and cameraLabel), then PATCHes chunks at the current Upload-Offset.
When the last byte lands the file is moved to originals/<video id>/ and a transcode job is
queued. HEAD returns the offset so an interrupted upload resumes where it stopped.
"""

from __future__ import annotations

import base64
import binascii
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.core.permissions import check_squad_role
from app.db import get_db, get_sessionmaker
from app.models import Event, Job, Role, Upload, UploadStatus, User, Video, VideoStatus
from app.schemas.event import UploadOut
from app.services.jobs import create_job, mark_failed
from app.services.storage import Storage, get_storage, safe_filename

log = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

TUS_VERSION = "1.0.0"
TUS_EXTENSIONS = "creation,termination,expiration"
CHUNK = 4 * 1024 * 1024


def _tus_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Tus-Resumable": TUS_VERSION, "Cache-Control": "no-store"}
    if extra:
        headers.update(extra)
    return headers


def _http_date(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _parse_metadata(raw: str | None) -> dict[str, str]:
    """Upload-Metadata is comma-separated `key base64value` pairs; the value may be absent."""
    result: dict[str, str] = {}
    if not raw:
        return result
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, _, value = pair.partition(" ")
        if value:
            try:
                decoded = base64.b64decode(value, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Upload-Metadata."
                ) from exc
        else:
            decoded = ""
        result[key] = decoded
    return result


def _load_owned_upload(db: Session, upload_id: uuid.UUID, user: User) -> Upload:
    upload = db.get(Upload, upload_id)
    if upload is None or upload.status in {UploadStatus.ABORTED, UploadStatus.EXPIRED}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    if upload.user_id != user.id and not user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    return upload


@router.options("", include_in_schema=False)
@router.options("/{upload_id}", include_in_schema=False)
def tus_options() -> Response:
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers=_tus_headers({"Tus-Version": TUS_VERSION, "Tus-Extension": TUS_EXTENSIONS}),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def tus_create(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    storage: Storage = Depends(get_storage),
) -> Response:
    length_raw = request.headers.get("Upload-Length")
    if length_raw is None or not length_raw.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload-Length is required (deferred length is not supported).",
        )
    length = int(length_raw)
    if length <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty.")

    meta = _parse_metadata(request.headers.get("Upload-Metadata"))
    event_id_raw = meta.get("eventId") or meta.get("event_id")
    try:
        event_id = uuid.UUID(event_id_raw or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a match for this video."
        ) from exc
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    check_squad_role(db, user, event.squad_id, Role.ANALYST)

    filename = safe_filename(meta.get("filename") or meta.get("name") or "video.mp4")
    camera_label = (meta.get("cameraLabel") or meta.get("camera_label") or "Main").strip()[:100]
    upload = Upload(
        user_id=user.id,
        squad_id=event.squad_id,
        event_id=event.id,
        camera_label=camera_label or "Main",
        filename=filename,
        size_bytes=length,
        offset_bytes=0,
        metadata_=meta,
        part_path="",
        expires_at=datetime.now(UTC) + timedelta(hours=settings.upload_expiry_hours),
    )
    db.add(upload)
    db.flush()
    part = storage.uploads_dir / f"{upload.id}.part"
    part.touch()
    upload.part_path = storage.relpath(part)
    db.commit()
    return Response(
        status_code=status.HTTP_201_CREATED,
        headers=_tus_headers(
            {
                "Location": f"{request.url.path.rstrip('/')}/{upload.id}",
                "Upload-Expires": _http_date(upload.expires_at),
            }
        ),
    )


@router.head("/{upload_id}", include_in_schema=False)
def tus_head(
    upload_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
) -> Response:
    upload = _load_owned_upload(db, upload_id, user)
    offset = upload.offset_bytes
    if upload.status == UploadStatus.IN_PROGRESS:
        part = storage.abspath(upload.part_path)
        offset = part.stat().st_size if part.exists() else 0
    return Response(
        status_code=status.HTTP_200_OK,
        headers=_tus_headers(
            {
                "Upload-Offset": str(offset),
                "Upload-Length": str(upload.size_bytes),
                "Upload-Expires": _http_date(upload.expires_at),
            }
        ),
    )


@router.patch("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def tus_patch(
    upload_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    storage: Storage = Depends(get_storage),
) -> Response:
    if request.headers.get("Content-Type") != "application/offset+octet-stream":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/offset+octet-stream.",
        )
    offset_raw = request.headers.get("Upload-Offset")
    if offset_raw is None or not offset_raw.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload-Offset is required."
        )
    client_offset = int(offset_raw)

    db = get_sessionmaker()()
    try:
        # Lock the row so two chunks for the same upload cannot interleave.
        upload = await run_in_threadpool(_lock_upload, db, upload_id, user)
        part = storage.abspath(upload.part_path)
        current = part.stat().st_size if part.exists() else 0
        if client_offset != current:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Upload-Offset {client_offset} does not match the server offset {current}.",
            )

        written = 0
        remaining = upload.size_bytes - current
        with part.open("ab") as fh:
            async for chunk in request.stream():
                if not chunk:
                    continue
                if written + len(chunk) > remaining:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="More data than Upload-Length.",
                    )
                fh.write(chunk)
                written += len(chunk)
        new_offset = current + written
        upload.offset_bytes = new_offset

        if new_offset == upload.size_bytes:
            await run_in_threadpool(_finalize, db, upload, user, storage, settings)
        else:
            db.commit()
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers=_tus_headers(
                {
                    "Upload-Offset": str(new_offset),
                    "Upload-Expires": _http_date(upload.expires_at),
                }
            ),
        )
    finally:
        db.close()


def _lock_upload(db: Session, upload_id: uuid.UUID, user: User) -> Upload:
    upload = db.scalar(select(Upload).where(Upload.id == upload_id).with_for_update())
    if upload is None or upload.status != UploadStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    if upload.user_id != user.id and not user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    if upload.expires_at <= datetime.now(UTC):
        upload.status = UploadStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="This upload expired. Start it again."
        )
    return upload


def _finalize(
    db: Session, upload: Upload, user: User, storage: Storage, settings: Settings
) -> None:
    """Move the completed file into place, create the video and queue the transcode."""
    video = Video(
        event_id=upload.event_id,
        camera_label=upload.camera_label,
        original_filename=upload.filename,
        original_path="",
        original_size_bytes=upload.size_bytes,
        status=VideoStatus.QUEUED,
        uploaded_by=user.id,
    )
    db.add(video)
    db.flush()
    dest_dir = storage.originals_dir(video.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest: Path = dest_dir / upload.filename
    part = storage.abspath(upload.part_path)
    part.replace(dest)  # same filesystem: atomic rename, no copy of a multi-GB file
    video.original_path = storage.relpath(dest)
    upload.status = UploadStatus.COMPLETED
    upload.video_id = video.id
    job = create_job(
        db,
        type_="transcode",
        queue="cpu",
        squad_id=upload.squad_id,
        video_id=video.id,
        created_by=user.id,
        input_={"video_id": str(video.id), "original": video.original_path},
    )
    db.commit()
    enqueue_transcode(db, job, video, settings)


def enqueue_transcode(db: Session, job: Job, video: Video, settings: Settings) -> None:
    from app.workers.tasks import transcode_video

    try:
        result = transcode_video.delay(str(job.id), str(video.id))
    except Exception as exc:  # broker down, or the eager run itself failed
        log.exception("could not queue transcode for video %s", video.id)
        db.rollback()
        db.refresh(job)
        if job.status not in {"failed", "succeeded"}:
            video.status = VideoStatus.FAILED
            video.error = "Could not start the job. Is the worker running?"
            mark_failed(db, job, f"Could not queue the job: {exc}")
        return
    db.refresh(job)
    if not settings.celery_task_always_eager:
        job.celery_task_id = result.id
        db.commit()


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def tus_terminate(
    upload_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
) -> Response:
    upload = _load_owned_upload(db, upload_id, user)
    if upload.status == UploadStatus.IN_PROGRESS:
        storage.abspath(upload.part_path).unlink(missing_ok=True)
        upload.status = UploadStatus.ABORTED
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_tus_headers())


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(
    upload_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Upload:
    """Plain JSON status for the UI (not part of the tus protocol)."""
    return _load_owned_upload(db, upload_id, user)
