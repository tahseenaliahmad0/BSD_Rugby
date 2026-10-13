from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import require_event, require_video
from app.db import get_db
from app.models import Event, Role, Video
from app.schemas.event import JobOut, VideoOut, VideoUpdate
from app.services.serializers import video_out
from app.services.storage import get_storage

router = APIRouter(tags=["videos"])


@router.get("/events/{event_id}/videos", response_model=list[VideoOut])
def list_videos(event: Event = Depends(require_event(Role.PLAYER))) -> list[VideoOut]:
    return [video_out(v) for v in event.videos]


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video: Video = Depends(require_video(Role.PLAYER))) -> VideoOut:
    return video_out(video)


@router.patch("/videos/{video_id}", response_model=VideoOut)
def update_video(
    body: VideoUpdate,
    video: Video = Depends(require_video(Role.ANALYST)),
    db: Session = Depends(get_db),
) -> VideoOut:
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(video, key, value)
    db.commit()
    return video_out(video)


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video: Video = Depends(require_video(Role.ADMIN)), db: Session = Depends(get_db)
) -> Response:
    get_storage().remove_video_files(video.id)
    db.delete(video)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/videos/{video_id}/jobs", response_model=list[JobOut])
def list_video_jobs(video: Video = Depends(require_video(Role.PLAYER))) -> list[JobOut]:
    return [JobOut.model_validate(j) for j in video.jobs]
