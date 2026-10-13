from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.clips import FilterDefinition


class CodeStat(BaseModel):
    code: str
    label: str
    colour: str | None
    count: int
    with_outcome: int
    successes: int
    success_rate: float | None
    filter: FilterDefinition
    success_filter: FilterDefinition | None
    failure_filter: FilterDefinition | None


class PlayerStat(BaseModel):
    player_id: uuid.UUID
    name: str
    shirt_number: int | None
    total: int
    by_code: dict[str, int] = Field(default_factory=dict)
    with_outcome: int
    successes: int
    success_rate: float | None
    filter: FilterDefinition


class StatsOut(BaseModel):
    event_id: uuid.UUID | None
    season_id: uuid.UUID | None
    template_name: str | None
    outcome_group: str | None
    success_values: list[str]
    tag_count: int
    codes: list[CodeStat]
    code_order: list[str]
    players: list[PlayerStat]
