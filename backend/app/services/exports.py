"""Exports: decide what to render, create the job, and run it in the worker."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Event, Export, Job, JobStatus, Playlist, Tag, User, Video, VideoStatus
from app.schemas.exports import ExportCreate, ExportOut
from app.services import clips as clip_svc
from app.services import playlists as playlist_svc
from app.services.export_render import ClipSpec, render
from app.services.jobs import (
    append_log,
    create_job,
    mark_failed,
    mark_started,
    mark_succeeded,
    set_progress,
)
from app.services.serializers import event_display_title
from app.services.storage import Storage, safe_filename
from app.services.tags import load_tag
from app.services.timeline import event_ms_to_video_seconds

log = logging.getLogger(__name__)


class ExportInputError(ValueError):
    pass


def _clip_entry(
    event: Event, video: Video | None, start_ms: int, end_ms: int, caption: str
) -> dict[str, Any]:
    chosen = video or clip_svc.playable_video(event)
    if chosen is None:
        raise ExportInputError(f"'{event_display_title(event)}' has no video to export from yet.")
    start_s = max(0.0, event_ms_to_video_seconds(start_ms, chosen.offset_ms))
    end_s = max(start_s + 0.1, event_ms_to_video_seconds(end_ms, chosen.offset_ms))
    if chosen.duration_s:
        end_s = min(end_s, chosen.duration_s)
    return {
        "video_id": str(chosen.id),
        "start_ms": round(start_s * 1000),
        "end_ms": round(end_s * 1000),
        "caption": caption,
    }


def _caption(code: str, note: str | None, event: Event) -> str:
    text = code
    if note:
        text += f" - {note}"
    return f"{text}  |  {event_display_title(event)}"


def plan_export(
    db: Session, squad_id: uuid.UUID, body: ExportCreate
) -> tuple[str, list[dict[str, Any]], uuid.UUID | None]:
    """Return (name, clips snapshot, playlist id) for an export request."""
    if body.kind == "clip":
        assert body.tag_id is not None
        tag = load_tag(db, body.tag_id)
        event = db.get(Event, tag.event_id) if tag else None
        if tag is None or event is None or event.squad_id != squad_id:
            raise ExportInputError("That tag does not exist.")
        name = body.name or f"{tag.code} - {event_display_title(event)}"
        return (
            name,
            [
                _clip_entry(
                    event, None, tag.start_ms, tag.end_ms, _caption(tag.code, tag.note, event)
                )
            ],
            None,
        )
    if body.kind == "range":
        assert body.range is not None
        event = db.get(Event, body.range.event_id)
        if event is None or event.squad_id != squad_id:
            raise ExportInputError("That match does not exist.")
        video = db.get(Video, body.range.video_id) if body.range.video_id else None
        name = body.name or f"Clip - {event_display_title(event)}"
        caption = _caption(body.range.note or "Clip", None, event)
        return (
            name,
            [_clip_entry(event, video, body.range.start_ms, body.range.end_ms, caption)],
            None,
        )
    assert body.playlist_id is not None
    playlist = playlist_svc.load_playlist(db, body.playlist_id)
    if playlist is None or playlist.squad_id != squad_id:
        raise ExportInputError("That playlist does not exist.")
    items = playlist_svc.items_out(db, playlist)
    if not items:
        raise ExportInputError("This playlist has no clips yet.")
    events = clip_svc.load_events(db, (i.event_id for i in items))
    clips = []
    for item in items:
        event = events[item.event_id]
        video = db.get(Video, item.clip.video.id) if item.clip.video else None
        src_tag: Tag | None = load_tag(db, item.tag_id) if item.tag_id else None
        caption = _caption(item.clip.code, item.note or (src_tag.note if src_tag else None), event)
        clips.append(_clip_entry(event, video, item.clip.start_ms, item.clip.end_ms, caption))
    return body.name or playlist.name, clips, playlist.id


def create_export(
    db: Session, squad_id: uuid.UUID, user: User, body: ExportCreate, settings: Settings
) -> Export:
    name, clips, playlist_id = plan_export(db, squad_id, body)
    export = Export(
        squad_id=squad_id,
        owner_id=user.id,
        name=name[:200],
        kind=body.kind,
        playlist_id=playlist_id,
        clips=clips,
        with_captions=body.with_captions,
        status=JobStatus.QUEUED,
    )
    db.add(export)
    db.flush()
    job = create_job(
        db,
        type_="export",
        queue="cpu",
        squad_id=squad_id,
        video_id=None,
        created_by=user.id,
        input_={"export_id": str(export.id), "clip_count": len(clips)},
    )
    export.job_id = job.id
    db.commit()

    from app.workers.tasks import export_video

    try:
        result = export_video.delay(str(export.id), str(job.id))
    except Exception as exc:  # broker down, or the eager run itself failed
        log.exception("could not queue export %s", export.id)
        db.rollback()
        db.refresh(job)
        db.refresh(export)
        if job.status not in {JobStatus.FAILED, JobStatus.SUCCEEDED}:
            mark_failed(db, job, f"Could not queue the job: {exc}")
            export.status = JobStatus.FAILED
            export.error = "Could not start the export. Is the worker running?"
            db.commit()
        return export
    db.refresh(export)
    if not settings.celery_task_always_eager:
        job.celery_task_id = result.id
        db.commit()
    return export


def run_export(
    db: Session, export_id: uuid.UUID, job_id: uuid.UUID, storage: Storage, settings: Settings
) -> None:
    export = db.get(Export, export_id)
    job = db.get(Job, job_id)
    if export is None or job is None:
        log.warning("export %s or job %s no longer exists", export_id, job_id)
        return
    export.status = JobStatus.RUNNING
    mark_started(db, job, "Preparing clips")
    try:
        specs: list[ClipSpec] = []
        for entry in export.clips:
            video = db.get(Video, uuid.UUID(entry["video_id"]))
            if video is None or video.status != VideoStatus.READY:
                raise ExportInputError("A video in this export is missing or not ready.")
            original = storage.abspath(video.original_path) if video.original_path else None
            if original is not None and original.exists():
                source = original
            elif video.proxy_path:
                source = storage.abspath(video.proxy_path)
                append_log(job, f"original missing for video {video.id}; using the proxy")
            else:
                raise ExportInputError("A video in this export has no file on disk.")
            specs.append(
                ClipSpec(
                    source=source,
                    start_s=entry["start_ms"] / 1000,
                    end_s=entry["end_ms"] / 1000,
                    caption=entry.get("caption") if export.with_captions else None,
                )
            )
        out_dir = storage.exports_dir(export.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / (safe_filename(export.name, "export") + ".mp4")

        def on_progress(fraction: float, message: str) -> None:
            export.progress = round(fraction, 3)
            set_progress(db, job, fraction, message)

        render(specs, target, settings, on_progress)
        export.file_path = storage.relpath(target)
        export.size_bytes = target.stat().st_size
        export.status = JobStatus.SUCCEEDED
        export.progress = 1.0
        export.finished_at = datetime.now(UTC)
        mark_succeeded(
            db,
            job,
            {"file": export.file_path, "size_bytes": export.size_bytes},
            "Ready to download",
        )
    except Exception as exc:
        log.exception("export %s failed", export.id)
        export.status = JobStatus.FAILED
        export.error = str(exc)[:2000]
        export.finished_at = datetime.now(UTC)
        mark_failed(db, job, str(exc))
        raise


def export_out(db: Session, export: Export) -> ExportOut:
    owner = db.get(User, export.owner_id) if export.owner_id else None
    return ExportOut(
        id=export.id,
        squad_id=export.squad_id,
        owner_id=export.owner_id,
        owner_name=owner.name if owner else None,
        name=export.name,
        kind=export.kind,
        status=export.status,
        progress=export.progress,
        with_captions=export.with_captions,
        clip_count=len(export.clips),
        file_url=Storage.media_url(export.file_path),
        size_bytes=export.size_bytes,
        error=export.error,
        job_id=export.job_id,
        created_at=export.created_at,
        finished_at=export.finished_at,
    )


def remove_export(db: Session, export: Export, storage: Storage) -> None:
    storage.remove_export_files(export.id)
    db.delete(export)


def playlist_for_export(db: Session, playlist_id: uuid.UUID) -> Playlist | None:
    return playlist_svc.load_playlist(db, playlist_id)
