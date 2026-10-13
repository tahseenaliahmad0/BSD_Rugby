"""Access control for video files.

Production: Caddy's `forward_auth` calls GET /api/media/authorize with the original request
in X-Forwarded-Uri; a 2xx lets Caddy's file_server serve the file with byte ranges.
Development: the API serves /media/<path> itself (range requests included).
"""

from __future__ import annotations

import re
import uuid
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.auth import get_optional_user
from app.core.permissions import squad_role
from app.db import get_db
from app.models import User, Video
from app.services.storage import MEDIA_PREFIX, Storage, get_storage

router = APIRouter(tags=["media"])

# proxies/<uuid>/{proxy.mp4,poster.jpg,thumbs/<n>.jpg,thumbs/thumbs.vtt}, originals/<uuid>/<file>
_ALLOWED = re.compile(
    r"^(?P<kind>proxies|originals)/(?P<video_id>[0-9a-f-]{36})/(?P<rest>[^/]+(?:/[^/]+)?)$"
)
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._ -]+$")

CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".vtt": "text/vtt",
}


def _authorize(db: Session, user: User | None, rel: str) -> Video:
    """Return the video if `user` may read the file at `rel` (relative to storage root)."""
    match = _ALLOWED.match(rel)
    if match is None or any(
        seg in {".", ".."} or not _SAFE_SEGMENT.match(seg) for seg in match["rest"].split("/")
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue."
        )
    video = db.get(Video, uuid.UUID(match["video_id"]))
    if video is None or squad_role(db, user, video.event.squad_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return video


def _rel_from_media_path(path: str) -> str:
    path = unquote(path)
    if not path.startswith(MEDIA_PREFIX):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return path[len(MEDIA_PREFIX) :]


@router.get("/api/media/authorize", include_in_schema=False)
def authorize_for_caddy(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    forwarded = request.headers.get("X-Forwarded-Uri") or request.headers.get("X-Original-URI")
    if not forwarded:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing URI.")
    rel = _rel_from_media_path(urlsplit(forwarded).path)
    _authorize(db, user, rel)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/media/{path:path}", include_in_schema=False)
def serve_media(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    settings: Settings = Depends(get_settings),
    storage: Storage = Depends(get_storage),
) -> Response:
    if not settings.api_serves_media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    rel = _rel_from_media_path(request.url.path)
    _authorize(db, user, rel)
    try:
        file = storage.abspath(rel)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from exc
    if not file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    media_type = CONTENT_TYPES.get(file.suffix.lower(), "application/octet-stream")
    return FileResponse(
        file,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600", "Accept-Ranges": "bytes"},
    )
