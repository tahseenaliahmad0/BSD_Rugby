"""Tags on the event timeline (integer milliseconds, ADR 0006; versioned, ADR 0007)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import TagSource
from app.schemas.common import ORMModel

_KEY_RE = re.compile(r"^[a-z0-9_]{1,50}$")
MAX_VALUE_LEN = 100
MAX_VALUES = 50


def validate_descriptors(value: dict[str, Any]) -> dict[str, Any]:
    """Descriptors are {group key: value | [values]} with short string values only."""
    if len(value) > 50:
        raise ValueError("Too many descriptor groups.")
    cleaned: dict[str, Any] = {}
    for key, raw in value.items():
        if not _KEY_RE.match(key):
            raise ValueError(f"Descriptor key {key!r} must be a short lower-case slug.")
        if raw is None or raw == "" or raw == []:
            continue
        if isinstance(raw, str):
            if len(raw) > MAX_VALUE_LEN:
                raise ValueError(f"Descriptor value for {key!r} is too long.")
            cleaned[key] = raw
        elif isinstance(raw, list):
            if len(raw) > MAX_VALUES or not all(
                isinstance(v, str) and 0 < len(v) <= MAX_VALUE_LEN for v in raw
            ):
                raise ValueError(f"Descriptor values for {key!r} must be short strings.")
            cleaned[key] = list(dict.fromkeys(raw))
        else:
            raise ValueError(f"Descriptor {key!r} must be a string or a list of strings.")
    return cleaned


class TagCreate(BaseModel):
    # A client may choose the id so that undo can restore a deleted tag under the same id.
    id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    code: str = Field(min_length=1, max_length=100)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    descriptors: dict[str, Any] = Field(default_factory=dict)
    player_ids: list[uuid.UUID] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=5000)
    source: TagSource = TagSource.MANUAL

    _check_descriptors = field_validator("descriptors")(validate_descriptors)

    @model_validator(mode="after")
    def _ordered(self) -> TagCreate:
        if self.end_ms < self.start_ms:
            raise ValueError("A tag cannot end before it starts.")
        return self


class TagUpdate(BaseModel):
    version: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    descriptors: dict[str, Any] | None = None
    player_ids: list[uuid.UUID] | None = None
    note: str | None = Field(default=None, max_length=5000)

    @field_validator("descriptors")
    @classmethod
    def _check_descriptors(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else validate_descriptors(value)


class TagRef(BaseModel):
    id: uuid.UUID
    version: int | None = Field(default=None, ge=1)


class TagBatch(BaseModel):
    """Several creates and deletes in one transaction (undo of a merge, bulk import, seeding)."""

    create: list[TagCreate] = Field(default_factory=list, max_length=5000)
    delete: list[TagRef] = Field(default_factory=list, max_length=5000)


class SplitIn(BaseModel):
    version: int = Field(ge=1)
    at_ms: int = Field(ge=0)


class MergeIn(BaseModel):
    tags: list[TagRef] = Field(min_length=2, max_length=500)


class TagOut(ORMModel):
    id: uuid.UUID
    event_id: uuid.UUID
    template_id: uuid.UUID | None
    code: str
    start_ms: int
    end_ms: int
    descriptors: dict[str, Any]
    player_ids: list[uuid.UUID]
    note: str | None
    source: TagSource
    version: int
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TagPair(BaseModel):
    left: TagOut
    right: TagOut


class BatchOut(BaseModel):
    created: list[TagOut]
    deleted: list[uuid.UUID]


class TagConflictOut(BaseModel):
    detail: str
    current: TagOut | None
