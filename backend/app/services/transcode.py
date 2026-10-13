"""The transcode pipeline: probe, proxy, poster, thumbnails. Runs inside a Celery task."""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Job, Video, VideoStatus
from app.services import ffmpeg
from app.services.jobs import append_log, mark_failed, mark_started, mark_succeeded, set_progress
from app.services.storage import Storage

log = logging.getLogger(__name__)


def transcode(db: Session, job: Job, video: Video, storage: Storage, settings: Settings) -> None:
    source = storage.abspath(video.original_path)
    out_dir = storage.proxies_dir(video.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    proxy_tmp = out_dir / "proxy.tmp.mp4"
    proxy = out_dir / "proxy.mp4"
    poster = out_dir / "poster.jpg"
    thumbs_dir = out_dir / "thumbs"

    video.status = VideoStatus.PROCESSING
    video.error = None
    mark_started(db, job, "Reading the file")
    append_log(job, f"source: {video.original_path}")

    try:
        info = ffmpeg.probe(source, settings)
        append_log(
            job,
            f"probe: {info.width}x{info.height} {info.fps} fps "
            f"{info.duration_s:.3f}s codec={info.video_codec} audio={info.has_audio}",
        )
        encoder = ffmpeg.choose_encoder(settings)
        append_log(job, f"encoder: {encoder}")
        set_progress(db, job, 0.0, "Making the playback copy")

        last_write = 0.0

        def on_progress(fraction: float) -> None:
            nonlocal last_write
            now = time.monotonic()
            if now - last_write >= 1.0 or fraction >= 1.0:
                last_write = now
                # Encoding is about 90% of the work; poster and thumbnails are the rest.
                set_progress(db, job, 0.9 * fraction)

        cmd = ffmpeg.proxy_command(source, proxy_tmp, info, settings, encoder)
        append_log(job, "ffmpeg " + " ".join(cmd[1:]))
        ffmpeg.run_with_progress(cmd, info.duration_s, on_progress)
        proxy_tmp.replace(proxy)

        set_progress(db, job, 0.9, "Making the poster and thumbnails")
        proxy_info = ffmpeg.probe(proxy, settings)
        ffmpeg.make_poster(proxy, poster, proxy_info.duration_s, settings)
        count = ffmpeg.make_thumbnails(
            proxy,
            thumbs_dir,
            proxy_info.duration_s,
            settings,
            on_progress=lambda fraction: set_progress(db, job, 0.9 + 0.1 * fraction),
        )

        video.proxy_path = storage.relpath(proxy)
        video.poster_path = storage.relpath(poster)
        video.thumbnails_path = storage.relpath(thumbs_dir)
        video.thumbnail_interval_s = settings.thumbnail_interval_s
        video.thumbnail_count = count
        video.fps_num = proxy_info.fps.numerator
        video.fps_den = proxy_info.fps.denominator
        video.duration_s = proxy_info.duration_s
        video.frame_count = proxy_info.frame_count or round(
            proxy_info.duration_s * proxy_info.fps_float
        )
        video.width = proxy_info.width
        video.height = proxy_info.height
        video.status = VideoStatus.READY
        mark_succeeded(
            db,
            job,
            {
                "encoder": encoder,
                "fps": str(proxy_info.fps),
                "duration_s": proxy_info.duration_s,
                "frame_count": video.frame_count,
                "width": proxy_info.width,
                "height": proxy_info.height,
                "thumbnail_count": count,
            },
            "Ready to watch",
        )
    except Exception as exc:
        log.exception("transcode failed for video %s", video.id)
        proxy_tmp.unlink(missing_ok=True)
        video.status = VideoStatus.FAILED
        video.error = str(exc)[:2000]
        append_log(job, f"error: {exc}")
        mark_failed(db, job, str(exc))
        raise


def transcode_by_ids(
    db: Session, job_id: uuid.UUID, video_id: uuid.UUID, storage: Storage, settings: Settings
) -> None:
    job = db.get(Job, job_id)
    video = db.get(Video, video_id)
    if job is None or video is None:
        log.warning("transcode: job %s or video %s no longer exists", job_id, video_id)
        return
    transcode(db, job, video, storage, settings)
