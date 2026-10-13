"""Clip search: a filter definition and the clips it returns."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models import EventType, TagSource
from app.schemas.common import ORMModel
from app.schemas.tags import TagOut


class FilterDefinition(BaseModel):
    """AND across fields, OR within a field. Empty fields do not filter."""

    codes: list[str] = Field(default_factory=list, max_length=100)
    # group key -> any of these values
    descriptors: dict[str, list[str]] = Field(default_factory=dict)
    player_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    event_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    season_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    opponent_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    event_types: list[EventType] = Field(default_factory=list)
    sources: list[TagSource] = Field(default_factory=list)
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    text: str | None = Field(default=None, max_length=200)

    @field_validator("descriptors")
    @classmethod
    def _clean(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        cleaned = {k: [v for v in vs if v] for k, vs in value.items()}
        return {k: vs for k, vs in cleaned.items() if vs}

    def is_empty(self) -> bool:
        return not any(
            [
                self.codes,
                self.descriptors,
                self.player_ids,
                self.event_ids,
                self.season_ids,
                self.opponent_ids,
                self.event_types,
                self.sources,
                self.date_from,
                self.date_to,
                self.text,
            ]
        )


class SearchIn(BaseModel):
    filter: FilterDefinition = Field(default_factory=FilterDefinition)
    limit: int = Field(default=200, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ClipEvent(BaseModel):
    id: uuid.UUID
    display_title: str
    date: dt.date
    opponent_name: str | None
    type: EventType


class ClipVideo(BaseModel):
    id: uuid.UUID
    proxy_url: str | None
    poster_url: str | None
    offset_ms: int
    fps_num: int | None
    fps_den: int | None
    duration_s: float | None
    thumbnail_url_template: str | None
    thumbnail_interval_s: int | None
    thumbnail_count: int | None


class ClipOut(BaseModel):
    """A tag or ad-hoc range ready to play: where it is and which video to play it from."""

    tag: TagOut | None
    event: ClipEvent
    video: ClipVideo | None
    code: str
    label: str
    start_ms: int
    end_ms: int
    # Video-relative seconds (None when the event has no ready video yet).
    start_s: float | None
    end_s: float | None
    thumbnail_url: str | None


class SearchOut(BaseModel):
    total: int
    clips: list[ClipOut]


class SavedFilterIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    definition: FilterDefinition
    is_shared: bool = False


class SavedFilterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    definition: FilterDefinition | None = None
    is_shared: bool | None = None


class SavedFilterOut(ORMModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    owner_id: uuid.UUID | None
    owner_name: str | None = None
    name: str
    definition: dict[str, Any]
    is_shared: bool
    created_at: dt.datetime
    updated_at: dt.datetime
