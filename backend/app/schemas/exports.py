from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models import JobStatus
from app.schemas.playlists import RangeIn


class ExportCreate(BaseModel):
    kind: Literal["clip", "playlist", "range"]
    name: str | None = Field(default=None, max_length=200)
    tag_id: uuid.UUID | None = None
    playlist_id: uuid.UUID | None = None
    range: RangeIn | None = None
    with_captions: bool = True

    @model_validator(mode="after")
    def _source_present(self) -> ExportCreate:
        needed = {"clip": self.tag_id, "playlist": self.playlist_id, "range": self.range}[self.kind]
        if needed is None:
            raise ValueError(f"A {self.kind} export needs a {self.kind} to export.")
        return self


class ExportOut(BaseModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    owner_id: uuid.UUID | None
    owner_name: str | None
    name: str
    kind: str
    status: JobStatus
    progress: float
    with_captions: bool
    clip_count: int
    file_url: str | None
    size_bytes: int | None
    error: str | None
    job_id: uuid.UUID | None
    created_at: dt.datetime
    finished_at: dt.datetime | None
