"""Playlists: visibility, building from filters or tags, resolving items into clips."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Event,
    Membership,
    Playlist,
    PlaylistItem,
    PlaylistShare,
    Role,
    Tag,
    User,
    Video,
)
from app.schemas.clips import FilterDefinition
from app.schemas.playlists import PlaylistItemOut, PlaylistOut, RangeIn, ShareOut
from app.services import clips as clip_svc
from app.services.tags import load_tag

MAX_FILTER_ITEMS = 1000


class PlaylistInputError(ValueError):
    pass


def can_view(playlist: Playlist, user: User, role: Role | None) -> bool:
    if user.is_superadmin or role == Role.ADMIN or playlist.owner_id == user.id:
        return True
    return any(s.user_id == user.id for s in playlist.shares)


def can_edit(playlist: Playlist, user: User, role: Role | None) -> bool:
    return user.is_superadmin or role == Role.ADMIN or playlist.owner_id == user.id


def visible_playlists(
    db: Session, squad_id: uuid.UUID, user: User, role: Role | None
) -> list[Playlist]:
    query = (
        select(Playlist)
        .where(Playlist.squad_id == squad_id)
        .options(selectinload(Playlist.shares), selectinload(Playlist.items))
        .order_by(Playlist.updated_at.desc())
    )
    if not (user.is_superadmin or role == Role.ADMIN):
        query = query.where(
            or_(
                Playlist.owner_id == user.id,
                Playlist.id.in_(
                    select(PlaylistShare.playlist_id).where(PlaylistShare.user_id == user.id)
                ),
            )
        )
    return list(db.scalars(query))


def load_playlist(db: Session, playlist_id: uuid.UUID) -> Playlist | None:
    return db.scalar(
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(selectinload(Playlist.shares), selectinload(Playlist.items))
    )


def _next_position(playlist: Playlist) -> int:
    return max((i.position for i in playlist.items), default=-1) + 1


def add_tags(db: Session, playlist: Playlist, tag_ids: Sequence[uuid.UUID]) -> list[PlaylistItem]:
    added: list[PlaylistItem] = []
    position = _next_position(playlist)
    for tag_id in dict.fromkeys(tag_ids):
        tag = db.get(Tag, tag_id)
        if tag is None:
            raise PlaylistInputError("One of the tags no longer exists.")
        event = db.get(Event, tag.event_id)
        if event is None or event.squad_id != playlist.squad_id:
            raise PlaylistInputError("Tags must belong to this squad.")
        item = PlaylistItem(
            playlist_id=playlist.id, position=position, tag_id=tag.id, event_id=tag.event_id
        )
        db.add(item)
        added.append(item)
        position += 1
    db.flush()
    db.expire(playlist, ["items"])
    return added


def add_ranges(db: Session, playlist: Playlist, ranges: Sequence[RangeIn]) -> list[PlaylistItem]:
    added: list[PlaylistItem] = []
    position = _next_position(playlist)
    for r in ranges:
        event = db.get(Event, r.event_id)
        if event is None or event.squad_id != playlist.squad_id:
            raise PlaylistInputError("Clips must come from this squad's matches.")
        if r.video_id is not None:
            video = db.get(Video, r.video_id)
            if video is None or video.event_id != event.id:
                raise PlaylistInputError("That video does not belong to the match.")
        item = PlaylistItem(
            playlist_id=playlist.id,
            position=position,
            event_id=event.id,
            video_id=r.video_id,
            start_ms=r.start_ms,
            end_ms=r.end_ms,
            note=r.note,
        )
        db.add(item)
        added.append(item)
        position += 1
    db.flush()
    db.expire(playlist, ["items"])
    return added


def rebuild_from_filter(db: Session, playlist: Playlist, definition: FilterDefinition) -> int:
    """Replace the items with the filter's current matches, keeping notes on tags still present."""
    notes = {i.tag_id: i.note for i in playlist.items if i.tag_id is not None and i.note}
    _, tags = clip_svc.search_tags(
        db, playlist.squad_id, definition, limit=MAX_FILTER_ITEMS, offset=0
    )
    for item in list(playlist.items):
        db.delete(item)
    db.flush()
    db.expire(playlist, ["items"])
    for position, tag in enumerate(tags):
        db.add(
            PlaylistItem(
                playlist_id=playlist.id,
                position=position,
                tag_id=tag.id,
                event_id=tag.event_id,
                note=notes.get(tag.id),
            )
        )
    db.flush()
    db.expire(playlist, ["items"])
    playlist.filter_definition = definition.model_dump(mode="json")
    return len(tags)


def reorder(playlist: Playlist, item_ids: Sequence[uuid.UUID]) -> None:
    by_id = {i.id: i for i in playlist.items}
    if set(item_ids) != set(by_id) or len(item_ids) != len(by_id):
        raise PlaylistInputError("The new order must list every clip exactly once.")
    for position, item_id in enumerate(item_ids):
        by_id[item_id].position = position


def set_shares(db: Session, playlist: Playlist, user_ids: Sequence[uuid.UUID]) -> None:
    members = set(
        db.scalars(
            select(Membership.user_id).where(
                Membership.squad_id == playlist.squad_id, Membership.user_id.in_(user_ids)
            )
        )
    )
    wanted = {u for u in user_ids if u != playlist.owner_id}
    if wanted - members:
        raise PlaylistInputError("You can only share with people in this squad.")
    for share in list(playlist.shares):
        if share.user_id not in wanted:
            db.delete(share)
    existing = {s.user_id for s in playlist.shares}
    for user_id in wanted - existing:
        db.add(PlaylistShare(playlist_id=playlist.id, user_id=user_id))
    db.flush()
    db.expire(playlist, ["shares"])


def duplicate(db: Session, playlist: Playlist, owner_id: uuid.UUID) -> Playlist:
    copy = Playlist(
        squad_id=playlist.squad_id,
        owner_id=owner_id,
        name=f"{playlist.name} (copy)"[:200],
        description=playlist.description,
        filter_definition=playlist.filter_definition,
        saved_filter_id=playlist.saved_filter_id,
    )
    db.add(copy)
    db.flush()
    for item in sorted(playlist.items, key=lambda i: i.position):
        db.add(
            PlaylistItem(
                playlist_id=copy.id,
                position=item.position,
                tag_id=item.tag_id,
                event_id=item.event_id,
                video_id=item.video_id,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                note=item.note,
            )
        )
    db.flush()
    return copy


def items_out(db: Session, playlist: Playlist) -> list[PlaylistItemOut]:
    items = sorted(playlist.items, key=lambda i: i.position)
    events = clip_svc.load_events(db, (i.event_id for i in items if i.event_id))
    out: list[PlaylistItemOut] = []
    for item in items:
        if item.tag_id is not None:
            tag = load_tag(db, item.tag_id)
            if tag is None:
                continue
            event = events.get(tag.event_id)
            if event is None:
                continue
            clip = clip_svc.clip_from_range(
                event,
                tag=tag,
                code=tag.code,
                label=tag.code,
                start_ms=tag.start_ms,
                end_ms=tag.end_ms,
            )
            event_id = tag.event_id
        else:
            if item.event_id is None or item.start_ms is None or item.end_ms is None:
                continue
            event = events.get(item.event_id)
            if event is None:
                continue
            video = db.get(Video, item.video_id) if item.video_id else None
            clip = clip_svc.clip_from_range(
                event,
                tag=None,
                code="Clip",
                label=item.note or "Clip",
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                video=video,
            )
            event_id = item.event_id
        out.append(
            PlaylistItemOut(
                id=item.id,
                position=item.position,
                note=item.note,
                tag_id=item.tag_id,
                event_id=event_id,
                clip=clip,
            )
        )
    return out


def playlist_out(
    db: Session, playlist: Playlist, user: User, role: Role | None, *, with_items: bool
) -> PlaylistOut:
    owner = db.get(User, playlist.owner_id) if playlist.owner_id else None
    share_users = (
        {
            u.id: u
            for u in db.scalars(
                select(User).where(User.id.in_([s.user_id for s in playlist.shares]))
            )
        }
        if playlist.shares
        else {}
    )
    return PlaylistOut(
        id=playlist.id,
        squad_id=playlist.squad_id,
        owner_id=playlist.owner_id,
        owner_name=owner.name if owner else None,
        name=playlist.name,
        description=playlist.description,
        filter_definition=playlist.filter_definition,
        saved_filter_id=playlist.saved_filter_id,
        item_count=len(playlist.items),
        can_edit=can_edit(playlist, user, role),
        shared_with=[
            ShareOut(user_id=s.user_id, name=share_users[s.user_id].name)
            for s in playlist.shares
            if s.user_id in share_users
        ],
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        items=items_out(db, playlist) if with_items else [],
    )
