"""Build API output models from ORM rows where a plain from_attributes mapping is not enough."""

from __future__ import annotations

from app.models import Event, EventType, Video
from app.schemas.event import EventOut, VideoOut
from app.services.storage import Storage


def video_out(video: Video) -> VideoOut:
    fps = video.fps_num / video.fps_den if video.fps_num and video.fps_den else None
    thumb_template = (
        Storage.media_url(f"{video.thumbnails_path}/{{index}}.jpg")
        if video.thumbnails_path
        else None
    )
    return VideoOut(
        id=video.id,
        event_id=video.event_id,
        camera_label=video.camera_label,
        original_filename=video.original_filename,
        original_size_bytes=video.original_size_bytes,
        status=video.status,
        error=video.error,
        fps_num=video.fps_num,
        fps_den=video.fps_den,
        fps=fps,
        duration_s=video.duration_s,
        frame_count=video.frame_count,
        width=video.width,
        height=video.height,
        offset_ms=video.offset_ms,
        thumbnail_interval_s=video.thumbnail_interval_s,
        thumbnail_count=video.thumbnail_count,
        proxy_url=Storage.media_url(video.proxy_path),
        poster_url=Storage.media_url(video.poster_path),
        thumbnail_url_template=thumb_template,
        original_url=Storage.media_url(video.original_path) or "",
        created_at=video.created_at,
        updated_at=video.updated_at,
    )


def event_display_title(event: Event) -> str:
    if event.title:
        return event.title
    if event.type == EventType.TRAINING:
        return "Training"
    if event.opponent is not None:
        return f"vs {event.opponent.name}"
    return "Match"


def event_out(event: Event, *, include_videos: bool) -> EventOut:
    videos = event.videos if include_videos else []
    return EventOut(
        id=event.id,
        squad_id=event.squad_id,
        season_id=event.season_id,
        opponent_id=event.opponent_id,
        opponent_name=event.opponent.name if event.opponent else None,
        type=event.type,
        title=event.title,
        display_title=event_display_title(event),
        date=event.date,
        kickoff_at=event.kickoff_at,
        venue=event.venue,
        competition=event.competition,
        is_home=event.is_home,
        notes=event.notes,
        created_at=event.created_at,
        updated_at=event.updated_at,
        video_count=len(event.videos),
        videos=[video_out(v) for v in videos],
    )
