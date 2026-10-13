from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import Role, SportVariant
from app.schemas.common import ORMModel


class SquadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sport_variant: SportVariant = SportVariant.FIFTEENS


class SquadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sport_variant: SportVariant | None = None


class SquadOut(ORMModel):
    id: uuid.UUID
    name: str
    sport_variant: SportVariant
    created_at: datetime
    my_role: Role | None = None


class MemberOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: Role
    is_active: bool


class MemberAdd(BaseModel):
    """Add an existing user by email, or create one if name and password are given."""

    email: EmailStr
    role: Role
    name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=1024)


class MemberUpdate(BaseModel):
    role: Role


class SeasonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None


class SeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None


class SeasonOut(ORMModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    name: str
    start_date: date | None
    end_date: date | None


class OpponentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    primary_colour: str | None = Field(default=None, max_length=32)
    secondary_colour: str | None = Field(default=None, max_length=32)


class OpponentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    primary_colour: str | None = Field(default=None, max_length=32)
    secondary_colour: str | None = Field(default=None, max_length=32)


class OpponentOut(ORMModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    name: str
    primary_colour: str | None
    secondary_colour: str | None


class PlayerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    shirt_number: int | None = Field(default=None, ge=0, le=99)
    position: str | None = Field(default=None, max_length=50)
    season_id: uuid.UUID | None = None


class PlayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    shirt_number: int | None = Field(default=None, ge=0, le=99)
    position: str | None = Field(default=None, max_length=50)
    season_id: uuid.UUID | None = None


class PlayerOut(ORMModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    season_id: uuid.UUID | None
    name: str
    shirt_number: int | None
    position: str | None
