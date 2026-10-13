"""Enumerations shared by models and API schemas."""

from __future__ import annotations

import enum


class SportVariant(enum.StrEnum):
    FIFTEENS = "fifteens"
    SEVENS = "sevens"


class Role(enum.StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    COACH = "coach"
    PLAYER = "player"


class EventType(enum.StrEnum):
    MATCH = "match"
    TRAINING = "training"


class VideoStatus(enum.StrEnum):
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class UploadStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"
    EXPIRED = "expired"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TagSource(enum.StrEnum):
    MANUAL = "manual"
    LIVE = "live"
    IMPORT = "import"
    AI = "ai"


class SuggestionStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ADJUSTED = "adjusted"


class LiveSyncState(enum.StrEnum):
    PENDING = "pending"
    SYNCED = "synced"
    ALIGNED = "aligned"


class ImportFormat(enum.StrEnum):
    SPORTSCODE_XML = "sportscode_xml"
    CSV = "csv"


class ImportStatus(enum.StrEnum):
    DRY_RUN = "dry_run"
    APPLIED = "applied"
    REVERTED = "reverted"
