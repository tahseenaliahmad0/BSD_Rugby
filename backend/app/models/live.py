"""Live sideline tagging sessions and their captured presses (Milestone 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.models.enums import LiveSyncState


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Client-generated so that re-uploads of the same session never duplicate it.
    client_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(200), nullable=False)
    wall_clock_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_offset_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sync_state: Mapped[LiveSyncState] = mapped_column(
        str_enum(LiveSyncState, "live_sync_state"), default=LiveSyncState.PENDING, nullable=False
    )
    # Period anchors pressed on the device: [{code, pressed_at}] and per-half offsets once aligned.
    anchors: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class LiveTag(Base):
    """One button press. The primary key is the client UUID, so uploads are idempotent."""

    __tablename__ = "live_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    live_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    pressed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    descriptors: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    tag_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
