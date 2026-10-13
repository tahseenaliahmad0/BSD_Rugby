from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_squad
from app.db import get_db
from app.models import Job, JobStatus, Role, Squad, User
from app.schemas.event import JobOut

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    if job.squad_id is not None:
        check_squad_role(db, user, job.squad_id, Role.PLAYER)
    elif not user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return JobOut.model_validate(job)


@router.get("/squads/{squad_id}/jobs", response_model=list[JobOut])
def list_squad_jobs(
    squad: Squad = Depends(require_squad(Role.COACH)),
    db: Session = Depends(get_db),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[JobOut]:
    query = select(Job).where(Job.squad_id == squad.id).order_by(Job.created_at.desc()).limit(limit)
    if status_filter is not None:
        query = query.where(Job.status == status_filter)
    return [JobOut.model_validate(j) for j in db.scalars(query)]
