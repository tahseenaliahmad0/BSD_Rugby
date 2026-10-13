"""Tag templates, tags, AI suggestions and the model registry (used from Milestone 2 on)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.models.enums import SuggestionStatus, TagSource


class TagTemplate(Base):
    """The code window for a squad: buttons and descriptor groups. Versioned."""

    __tablename__ = "tag_templates"
    __table_args__ = (
        UniqueConstraint("family_id", "version", name="uq_tag_templates_family_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # All versions of one template share a family id; `is_active` marks the current version.
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # [{code, label, hotkey, colour, kind: instant|span, lead_ms, lag_ms, groups: [group key]}]
    buttons: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    # [{key, label, kind: options|players, multiple, options: [{value, label, hotkey}]}]
    descriptor_groups: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    # Which descriptor group holds the outcome, and which of its values count as success.
    outcome_group: Mapped[str | None] = mapped_column(String(50))
    success_values: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()


class Tag(Base):
    """A tagged moment on an event's timeline (seconds from event timeline zero)."""

    __tablename__ = "tags"
    __table_args__ = (
        Index("ix_tags_event_start", "event_id", "start_ms"),
        Index("ix_tags_event_code", "event_id", "code"),
        Index("ix_tags_descriptors", "descriptors", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tag_templates.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Integer milliseconds on the event timeline (ADR 0006).
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    descriptors: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    # Optimistic concurrency (ADR 0007): every update must carry the version it last saw.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[TagSource] = mapped_column(
        str_enum(TagSource, "tag_source"), default=TagSource.MANUAL, nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    live_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live_sessions.id", ondelete="SET NULL")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    players: Mapped[list[TagPlayer]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class TagPlayer(Base):
    __tablename__ = "tag_players"

    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_versions_name_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    task: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = created_at_col()


class Suggestion(Base):
    """An AI-proposed tag. Kept forever as training and evaluation data."""

    __tablename__ = "suggestions"
    __table_args__ = (Index("ix_suggestions_video_status", "video_id", "status"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    # Video-relative milliseconds; the video offset maps them onto the event timeline.
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[SuggestionStatus] = mapped_column(
        str_enum(SuggestionStatus, "suggestion_status"),
        default=SuggestionStatus.PENDING,
        nullable=False,
    )
    tag_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
