from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import Role
from app.schemas.common import ORMModel


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class MembershipSummary(BaseModel):
    squad_id: uuid.UUID
    squad_name: str
    role: Role


class UserOut(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    is_superadmin: bool
    created_at: datetime


class MeOut(UserOut):
    memberships: list[MembershipSummary]
    csrf_token: str


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    is_superadmin: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=1024)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=1024)
