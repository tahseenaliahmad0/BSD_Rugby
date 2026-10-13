"""Create jobs and record their progress."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, JobStatus


def create_job(
    db: Session,
    *,
    type_: str,
    queue: str,
    squad_id: uuid.UUID | None,
    video_id: uuid.UUID | None,
    created_by: uuid.UUID | None,
    input_: dict[str, Any] | None = None,
) -> Job:
    job = Job(
        type=type_,
        queue=queue,
        squad_id=squad_id,
        video_id=video_id,
        created_by=created_by,
        input=input_ or {},
        message="Waiting for a worker",
    )
    db.add(job)
    db.flush()
    return job


def mark_started(db: Session, job: Job, message: str) -> None:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    job.message = message
    job.progress = 0.0
    db.commit()


def set_progress(db: Session, job: Job, progress: float, message: str | None = None) -> None:
    job.progress = round(progress, 4)
    if message is not None:
        job.message = message
    db.commit()


def append_log(job: Job, line: str) -> None:
    job.log = (job.log or "") + line.rstrip() + "\n"


def mark_succeeded(db: Session, job: Job, output: dict[str, Any], message: str) -> None:
    job.status = JobStatus.SUCCEEDED
    job.progress = 1.0
    job.output = output
    job.message = message
    job.finished_at = datetime.now(UTC)
    db.commit()


def mark_failed(db: Session, job: Job, error: str) -> None:
    job.status = JobStatus.FAILED
    job.error = error[:4000]
    job.message = "Failed"
    job.finished_at = datetime.now(UTC)
    db.commit()
