from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models import EventType, JobStatus, UploadStatus, VideoStatus
from app.schemas.common import ORMModel


class EventCreate(BaseModel):
    type: EventType = EventType.MATCH
    date: dt.date
    title: str | None = Field(default=None, max_length=200)
    season_id: uuid.UUID | None = None
    opponent_id: uuid.UUID | None = None
    # Convenience: name a new or existing opponent instead of passing its id.
    opponent_name: str | None = Field(default=None, max_length=200)
    kickoff_at: dt.datetime | None = None
    venue: str | None = Field(default=None, max_length=200)
    competition: str | None = Field(default=None, max_length=200)
    is_home: bool | None = None
    notes: str | None = None


class EventUpdate(BaseModel):
    type: EventType | None = None
    date: dt.date | None = None
    title: str | None = Field(default=None, max_length=200)
    season_id: uuid.UUID | None = None
    opponent_id: uuid.UUID | None = None
    kickoff_at: dt.datetime | None = None
    venue: str | None = Field(default=None, max_length=200)
    competition: str | None = Field(default=None, max_length=200)
    is_home: bool | None = None
    notes: str | None = None


class VideoOut(ORMModel):
    id: uuid.UUID
    event_id: uuid.UUID
    camera_label: str
    original_filename: str
    original_size_bytes: int
    status: VideoStatus
    error: str | None
    fps_num: int | None
    fps_den: int | None
    fps: float | None
    duration_s: float | None
    frame_count: int | None
    width: int | None
    height: int | None
    offset_s: float
    thumbnail_interval_s: int | None
    thumbnail_count: int | None
    proxy_url: str | None
    poster_url: str | None
    thumbnail_url_template: str | None
    original_url: str
    created_at: dt.datetime
    updated_at: dt.datetime


class VideoUpdate(BaseModel):
    camera_label: str | None = Field(default=None, min_length=1, max_length=100)
    offset_s: float | None = None


class EventOut(ORMModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    season_id: uuid.UUID | None
    opponent_id: uuid.UUID | None
    opponent_name: str | None
    type: EventType
    title: str | None
    display_title: str
    date: dt.date
    kickoff_at: dt.datetime | None
    venue: str | None
    competition: str | None
    is_home: bool | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    video_count: int
    videos: list[VideoOut] = Field(default_factory=list)


class JobOut(ORMModel):
    id: uuid.UUID
    type: str
    queue: str
    status: JobStatus
    progress: float
    message: str | None
    error: str | None
    log: str | None = None
    video_id: uuid.UUID | None
    squad_id: uuid.UUID | None
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    output: dict[str, Any] = Field(default_factory=dict)


class UploadOut(ORMModel):
    id: uuid.UUID
    event_id: uuid.UUID
    filename: str
    size_bytes: int
    offset_bytes: int
    status: UploadStatus
    video_id: uuid.UUID | None
    created_at: dt.datetime
    expires_at: dt.datetime
