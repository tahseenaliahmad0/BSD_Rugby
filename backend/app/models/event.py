"""Events (matches and training sessions), videos, uploads and background jobs."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col, str_enum, updated_at_col, uuid_pk
from app.models.enums import EventType, JobStatus, UploadStatus, VideoStatus
from app.models.squad import Opponent, Season, Squad
from app.models.user import User


class Event(Base):
    """Owns the timeline that tags, videos, live sessions and imports hang on."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_squad_date", "squad_id", "date"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="SET NULL"), index=True
    )
    opponent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opponents.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[EventType] = mapped_column(str_enum(EventType, "event_type"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    kickoff_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str | None] = mapped_column(String(200))
    competition: Mapped[str | None] = mapped_column(String(200))
    is_home: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = created_at_col()
    updated_at: Mapped[dt.datetime] = updated_at_col()

    squad: Mapped[Squad] = relationship()
    season: Mapped[Season | None] = relationship()
    opponent: Mapped[Opponent | None] = relationship()
    videos: Mapped[list[Video]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Video.created_at",
    )


class Video(Base):
    """One camera file for an event. The original is never modified."""

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_label: Mapped[str] = mapped_column(String(100), default="Main", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    proxy_path: Mapped[str | None] = mapped_column(String(1000))
    poster_path: Mapped[str | None] = mapped_column(String(1000))
    thumbnails_path: Mapped[str | None] = mapped_column(String(1000))
    thumbnail_interval_s: Mapped[int | None] = mapped_column(Integer)
    thumbnail_count: Mapped[int | None] = mapped_column(Integer)
    # Exact frame rate of the proxy, as a rational (for example 30000/1001).
    fps_num: Mapped[int | None] = mapped_column(Integer)
    fps_den: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    frame_count: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    # Seconds on the event timeline at which this video starts (video time = event time - offset).
    offset_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[VideoStatus] = mapped_column(
        str_enum(VideoStatus, "video_status"), default=VideoStatus.QUEUED, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = created_at_col()
    updated_at: Mapped[dt.datetime] = updated_at_col()

    event: Mapped[Event] = relationship(back_populates="videos")
    jobs: Mapped[list[Job]] = relationship(
        back_populates="video",
        order_by="Job.created_at",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Upload(Base):
    """A tus upload in progress or just completed."""

    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_label: Mapped[str] = mapped_column(String(100), default="Main", nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offset_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    part_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        str_enum(UploadStatus, "upload_status"), default=UploadStatus.IN_PROGRESS, nullable=False
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL")
    )
    created_at: Mapped[dt.datetime] = created_at_col()
    updated_at: Mapped[dt.datetime] = updated_at_col()
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship()


class Job(Base):
    """A background job (transcode, import, export, AI) with progress and a log."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    queue: Mapped[str] = mapped_column(String(20), default="cpu", nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "job_status"), default=JobStatus.QUEUED, nullable=False
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    log: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    squad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[dt.datetime] = created_at_col()
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    video: Mapped[Video | None] = relationship(back_populates="jobs")
