"""Squads, memberships, seasons, opponents and players."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col, str_enum, uuid_pk
from app.models.enums import Role, SportVariant
from app.models.user import User


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    sport_variant: Mapped[SportVariant] = mapped_column(
        str_enum(SportVariant, "sport_variant"), default=SportVariant.FIFTEENS, nullable=False
    )
    created_at: Mapped[datetime] = created_at_col()

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="squad", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "squad_id", name="uq_memberships_user_squad"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[Role] = mapped_column(str_enum(Role, "membership_role"), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    user: Mapped[User] = relationship(back_populates="memberships")
    squad: Mapped[Squad] = relationship(back_populates="memberships")


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("squad_id", "name", name="uq_seasons_squad_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = created_at_col()


class Opponent(Base):
    __tablename__ = "opponents"
    __table_args__ = (UniqueConstraint("squad_id", "name", name="uq_opponents_squad_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_colour: Mapped[str | None] = mapped_column(String(32))
    secondary_colour: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_at_col()


class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = uuid_pk()
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = created_at_col()
