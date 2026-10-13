from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.clips import ClipOut, FilterDefinition


class RangeIn(BaseModel):
    """An ad-hoc clip: a stretch of an event's timeline, optionally pinned to one video."""

    event_id: uuid.UUID
    video_id: uuid.UUID | None = None
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _ordered(self) -> RangeIn:
        if self.end_ms <= self.start_ms:
            raise ValueError("A clip must end after it starts.")
        return self


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    # Build from a filter (snapshot now; refresh later), from tags, or start empty.
    filter: FilterDefinition | None = None
    saved_filter_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    ranges: list[RangeIn] = Field(default_factory=list, max_length=1000)


class PlaylistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    filter: FilterDefinition | None = None


class ItemsAdd(BaseModel):
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)
    ranges: list[RangeIn] = Field(default_factory=list, max_length=1000)


class ItemUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)


class OrderIn(BaseModel):
    item_ids: list[uuid.UUID] = Field(max_length=5000)


class SharesIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(max_length=200)


class ShareOut(BaseModel):
    user_id: uuid.UUID
    name: str


class PlaylistItemOut(BaseModel):
    id: uuid.UUID
    position: int
    note: str | None
    tag_id: uuid.UUID | None
    event_id: uuid.UUID
    clip: ClipOut


class PlaylistOut(BaseModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    owner_id: uuid.UUID | None
    owner_name: str | None
    name: str
    description: str | None
    filter_definition: dict[str, Any] | None
    saved_filter_id: uuid.UUID | None
    item_count: int
    can_edit: bool
    shared_with: list[ShareOut]
    created_at: dt.datetime
    updated_at: dt.datetime
    items: list[PlaylistItemOut] = Field(default_factory=list)
