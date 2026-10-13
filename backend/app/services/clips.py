"""Turn a filter definition into SQL over tags and events, and resolve tags into playable clips.

Descriptor conditions use JSONB containment (`@>`), which the GIN index on `tags.descriptors`
serves. A value may be stored as a scalar or inside a list (multi-select groups), so both
shapes are tried: `descriptors @> {"zone": "Opp 22"}` OR `descriptors @> {"zone": ["Opp 22"]}`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Event, Tag, TagPlayer, Video, VideoStatus
from app.schemas.clips import ClipEvent, ClipOut, ClipVideo, FilterDefinition
from app.services.serializers import event_display_title
from app.services.storage import Storage
from app.services.tags import tag_out
from app.services.timeline import event_ms_to_video_seconds


def apply_filter(query: Select[Any], squad_id: uuid.UUID, f: FilterDefinition) -> Select[Any]:
    """Add the WHERE clauses for `f` to a query that already joins Tag and Event."""
    query = query.where(Event.squad_id == squad_id)
    if f.codes:
        query = query.where(Tag.code.in_(f.codes))
    for key, values in f.descriptors.items():
        alternatives = []
        for value in values:
            alternatives.append(Tag.descriptors.contains({key: value}))
            alternatives.append(Tag.descriptors.contains({key: [value]}))
        query = query.where(or_(*alternatives))
    if f.player_ids:
        query = query.where(
            exists(
                select(TagPlayer.tag_id).where(
                    TagPlayer.tag_id == Tag.id, TagPlayer.player_id.in_(f.player_ids)
                )
            )
        )
    if f.event_ids:
        query = query.where(Tag.event_id.in_(f.event_ids))
    if f.season_ids:
        query = query.where(Event.season_id.in_(f.season_ids))
    if f.opponent_ids:
        query = query.where(Event.opponent_id.in_(f.opponent_ids))
    if f.event_types:
        query = query.where(Event.type.in_(f.event_types))
    if f.sources:
        query = query.where(Tag.source.in_(f.sources))
    if f.date_from is not None:
        query = query.where(Event.date >= f.date_from)
    if f.date_to is not None:
        query = query.where(Event.date <= f.date_to)
    if f.text:
        query = query.where(Tag.note.ilike(f"%{f.text.strip()}%"))
    return query


def search_tags(
    db: Session, squad_id: uuid.UUID, f: FilterDefinition, *, limit: int, offset: int
) -> tuple[int, list[Tag]]:
    base = apply_filter(select(Tag).join(Event, Tag.event_id == Event.id), squad_id, f)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.options(selectinload(Tag.players))
        .order_by(Event.date.desc(), Event.created_at.desc(), Tag.start_ms, Tag.created_at)
        .limit(limit)
        .offset(offset)
    ).all()
    return int(total), list(rows)


def playable_video(event: Event) -> Video | None:
    """The video a clip plays from: the first ready one."""
    return next((v for v in event.videos if v.status == VideoStatus.READY), None)


def clip_video(video: Video | None) -> ClipVideo | None:
    if video is None:
        return None
    return ClipVideo(
        id=video.id,
        proxy_url=Storage.media_url(video.proxy_path),
        poster_url=Storage.media_url(video.poster_path),
        offset_ms=video.offset_ms,
        fps_num=video.fps_num,
        fps_den=video.fps_den,
        duration_s=video.duration_s,
        thumbnail_url_template=Storage.media_url(f"{video.thumbnails_path}/{{index}}.jpg")
        if video.thumbnails_path
        else None,
        thumbnail_interval_s=video.thumbnail_interval_s,
        thumbnail_count=video.thumbnail_count,
    )


def thumbnail_for(video: Video | None, start_s: float | None) -> str | None:
    if (
        video is None
        or start_s is None
        or not video.thumbnails_path
        or not video.thumbnail_interval_s
        or not video.thumbnail_count
    ):
        return None
    index = min(video.thumbnail_count, max(1, int(start_s // video.thumbnail_interval_s) + 1))
    return Storage.media_url(f"{video.thumbnails_path}/{index:05d}.jpg")


def clip_from_range(
    event: Event,
    *,
    tag: Tag | None,
    code: str,
    label: str,
    start_ms: int,
    end_ms: int,
    video: Video | None = None,
) -> ClipOut:
    chosen = video or playable_video(event)
    start_s = end_s = None
    if chosen is not None:
        start_s = max(0.0, event_ms_to_video_seconds(start_ms, chosen.offset_ms))
        end_s = max(start_s, event_ms_to_video_seconds(end_ms, chosen.offset_ms))
    return ClipOut(
        tag=tag_out(tag) if tag is not None else None,
        event=ClipEvent(
            id=event.id,
            display_title=event_display_title(event),
            date=event.date,
            opponent_name=event.opponent.name if event.opponent else None,
            type=event.type,
        ),
        video=clip_video(chosen),
        code=code,
        label=label,
        start_ms=start_ms,
        end_ms=end_ms,
        start_s=start_s,
        end_s=end_s,
        thumbnail_url=thumbnail_for(chosen, start_s),
    )


def load_events(db: Session, event_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Event]:
    ids = list(set(event_ids))
    if not ids:
        return {}
    events = db.scalars(
        select(Event)
        .where(Event.id.in_(ids))
        .options(selectinload(Event.videos), selectinload(Event.opponent))
    ).all()
    return {e.id: e for e in events}


def clips_for_tags(db: Session, tags: Sequence[Tag]) -> list[ClipOut]:
    events = load_events(db, (t.event_id for t in tags))
    return [
        clip_from_range(
            events[t.event_id],
            tag=t,
            code=t.code,
            label=t.code,
            start_ms=t.start_ms,
            end_ms=t.end_ms,
        )
        for t in tags
        if t.event_id in events
    ]
