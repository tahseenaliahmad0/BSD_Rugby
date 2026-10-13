"""Where files live on disk.

Paths stored in the database are relative to STORAGE_ROOT so the volume can move between
hosts and containers. The layout is:

    uploads/<upload id>.part          tus upload in progress
    originals/<video id>/<filename>   the untouched upload (never rewritten)
    proxies/<video id>/proxy.mp4      browser-friendly H.264/AAC proxy
    proxies/<video id>/poster.jpg
    proxies/<video id>/thumbs/00001.jpg ... and thumbs.vtt
"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from app.config import get_settings

MEDIA_PREFIX = "/media/"
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(name: str, fallback: str = "video.mp4") -> str:
    """Keep the original name recognisable but safe to put on disk and in a URL."""
    base = Path(name).name
    cleaned = _SAFE_CHARS.sub("_", base).strip(" .")
    return cleaned[:200] or fallback


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    # Directories --------------------------------------------------------------------------
    @property
    def uploads_dir(self) -> Path:
        return self.root / "uploads"

    def originals_dir(self, video_id: uuid.UUID) -> Path:
        return self.root / "originals" / str(video_id)

    def proxies_dir(self, video_id: uuid.UUID) -> Path:
        return self.root / "proxies" / str(video_id)

    def ensure_dirs(self) -> None:
        for d in (self.uploads_dir, self.root / "originals", self.root / "proxies"):
            d.mkdir(parents=True, exist_ok=True)

    # Relative / absolute conversion ---------------------------------------------------------
    def relpath(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def abspath(self, rel: str) -> Path:
        candidate = (self.root / rel).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("path escapes storage root")
        return candidate

    @staticmethod
    def media_url(rel: str | None) -> str | None:
        return None if rel is None else MEDIA_PREFIX + rel

    # Deletion -----------------------------------------------------------------------------
    def remove_video_files(self, video_id: uuid.UUID) -> None:
        for d in (self.originals_dir(video_id), self.proxies_dir(video_id)):
            shutil.rmtree(d, ignore_errors=True)


def get_storage() -> Storage:
    storage = Storage(get_settings().storage_root)
    storage.ensure_dirs()
    return storage
