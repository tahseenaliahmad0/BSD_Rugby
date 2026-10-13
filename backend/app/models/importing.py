"""Hudl / Sportscode import batches (Milestone 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, str_enum, uuid_pk
from app.models.enums import ImportFormat, ImportStatus


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = uuid_pk()
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(1000))
    format: Mapped[ImportFormat] = mapped_column(str_enum(ImportFormat, "import_format"))
    code_mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    alignment_offset_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        str_enum(ImportStatus, "import_status"), default=ImportStatus.DRY_RUN, nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
