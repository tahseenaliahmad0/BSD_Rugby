"""Celery tasks. Keep them thin: the work lives in app.services."""

from __future__ import annotations

import uuid

from app.config import get_settings
from app.db import get_sessionmaker
from app.services.storage import get_storage
from app.services.transcode import transcode_by_ids
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.transcode_video")
def transcode_video(job_id: str, video_id: str) -> None:
    db = get_sessionmaker()()
    try:
        transcode_by_ids(db, uuid.UUID(job_id), uuid.UUID(video_id), get_storage(), get_settings())
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.gpu_ping")
def gpu_ping() -> dict[str, str]:
    """Placeholder for the gpu queue so the worker-gpu service has something to run."""
    return {"status": "ok", "queue": "gpu"}
