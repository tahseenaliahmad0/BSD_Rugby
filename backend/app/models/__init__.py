"""All ORM models. Import this module so that every table is registered on Base.metadata."""

from app.models.base import Base
from app.models.enums import (
    EventType,
    ImportFormat,
    ImportStatus,
    JobStatus,
    LiveSyncState,
    Role,
    SportVariant,
    SuggestionStatus,
    TagSource,
    UploadStatus,
    VideoStatus,
)
from app.models.event import Event, Job, Upload, Video
from app.models.export import Export
from app.models.filters import SavedFilter
from app.models.importing import ImportBatch
from app.models.live import LiveSession, LiveTag
from app.models.playlist import Drawing, Playlist, PlaylistItem, PlaylistShare
from app.models.squad import Membership, Opponent, Player, Season, Squad
from app.models.tagging import ModelVersion, Suggestion, Tag, TagPlayer, TagTemplate
from app.models.user import User, UserSession

__all__ = [
    "Base",
    "Drawing",
    "Event",
    "EventType",
    "Export",
    "ImportBatch",
    "ImportFormat",
    "ImportStatus",
    "Job",
    "JobStatus",
    "LiveSession",
    "LiveSyncState",
    "LiveTag",
    "Membership",
    "ModelVersion",
    "Opponent",
    "Player",
    "Playlist",
    "PlaylistItem",
    "PlaylistShare",
    "Role",
    "SavedFilter",
    "Season",
    "SportVariant",
    "Squad",
    "Suggestion",
    "SuggestionStatus",
    "Tag",
    "TagPlayer",
    "TagSource",
    "TagTemplate",
    "Upload",
    "UploadStatus",
    "User",
    "UserSession",
    "Video",
    "VideoStatus",
]
