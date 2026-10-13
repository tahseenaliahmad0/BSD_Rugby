"""Tag persistence with optimistic concurrency (ADR 0007)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.models import Event, Player, Tag, TagPlayer, TagTemplate
from app.schemas.tags import TagCreate, TagOut, TagRef, TagUpdate


class TagConflict(Exception):
    """Someone else changed the tag since the client last saw it."""

    def __init__(self, current: Tag | None) -> None:
        super().__init__("conflict")
        self.current = current


class TagInputError(ValueError):
    pass


def tag_out(tag: Tag) -> TagOut:
    return TagOut(
        id=tag.id,
        event_id=tag.event_id,
        template_id=tag.template_id,
        code=tag.code,
        start_ms=tag.start_ms,
        end_ms=tag.end_ms,
        descriptors=tag.descriptors,
        player_ids=[tp.player_id for tp in tag.players],
        note=tag.note,
        source=tag.source,
        version=tag.version,
        created_by=tag.created_by,
        updated_by=tag.updated_by,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
    )


def load_tag(db: Session, tag_id: uuid.UUID) -> Tag | None:
    return db.scalar(select(Tag).where(Tag.id == tag_id).options(selectinload(Tag.players)))


def list_event_tags(db: Session, event_id: uuid.UUID) -> list[Tag]:
    return list(
        db.scalars(
            select(Tag)
            .where(Tag.event_id == event_id)
            .options(selectinload(Tag.players))
            .order_by(Tag.start_ms, Tag.created_at)
        )
    )


def _check_players(db: Session, squad_id: uuid.UUID, player_ids: list[uuid.UUID]) -> None:
    if not player_ids:
        return
    found = set(
        db.scalars(select(Player.id).where(Player.id.in_(player_ids), Player.squad_id == squad_id))
    )
    missing = [str(p) for p in player_ids if p not in found]
    if missing:
        raise TagInputError("Some players are not in this squad.")


def _check_template(db: Session, squad_id: uuid.UUID, template_id: uuid.UUID | None) -> None:
    if template_id is None:
        return
    template = db.get(TagTemplate, template_id)
    if template is None or template.squad_id != squad_id:
        raise TagInputError("That template is not in this squad.")


def _set_players(db: Session, tag: Tag, player_ids: list[uuid.UUID]) -> None:
    db.execute(delete(TagPlayer).where(TagPlayer.tag_id == tag.id))
    for pid in dict.fromkeys(player_ids):
        db.add(TagPlayer(tag_id=tag.id, player_id=pid))
    db.flush()
    db.expire(tag, ["players"])


def create_tag(db: Session, event: Event, data: TagCreate, user_id: uuid.UUID | None) -> Tag:
    _check_players(db, event.squad_id, data.player_ids)
    _check_template(db, event.squad_id, data.template_id)
    if data.id is not None and db.get(Tag, data.id) is not None:
        raise TagInputError("A tag with that id already exists.")
    tag = Tag(
        event_id=event.id,
        template_id=data.template_id,
        code=data.code.strip(),
        start_ms=data.start_ms,
        end_ms=data.end_ms,
        descriptors=data.descriptors,
        note=data.note,
        source=data.source,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )
    if data.id is not None:
        tag.id = data.id
    db.add(tag)
    db.flush()
    _set_players(db, tag, data.player_ids)
    return reload(db, tag.id)


def reload(db: Session, tag_id: uuid.UUID) -> Tag:
    tag = load_tag(db, tag_id)
    assert tag is not None
    db.refresh(tag)
    return tag


def _bump(db: Session, tag: Tag, expected_version: int, values: dict[str, Any]) -> None:
    """Apply `values` only if the row still has `expected_version`; raise TagConflict otherwise."""
    result = db.execute(
        update(Tag)
        .where(Tag.id == tag.id, Tag.version == expected_version)
        .values(version=Tag.version + 1, **values)
    )
    assert isinstance(result, CursorResult)
    if result.rowcount != 1:
        db.rollback()
        raise TagConflict(load_tag(db, tag.id))


def update_tag(
    db: Session, tag: Tag, data: TagUpdate, squad_id: uuid.UUID, user_id: uuid.UUID | None
) -> Tag:
    values: dict[str, Any] = {"updated_by": user_id}
    if data.code is not None:
        values["code"] = data.code.strip()
    if data.start_ms is not None:
        values["start_ms"] = data.start_ms
    if data.end_ms is not None:
        values["end_ms"] = data.end_ms
    if data.descriptors is not None:
        values["descriptors"] = data.descriptors
    if "note" in data.model_fields_set:
        values["note"] = data.note
    new_start = values.get("start_ms", tag.start_ms)
    new_end = values.get("end_ms", tag.end_ms)
    if new_end < new_start:
        raise TagInputError("A tag cannot end before it starts.")
    if data.player_ids is not None:
        _check_players(db, squad_id, data.player_ids)
    _bump(db, tag, data.version, values)
    if data.player_ids is not None:
        _set_players(db, tag, data.player_ids)
    return reload(db, tag.id)


def delete_tag(db: Session, tag: Tag, expected_version: int | None) -> None:
    stmt = delete(Tag).where(Tag.id == tag.id)
    if expected_version is not None:
        stmt = stmt.where(Tag.version == expected_version)
    result = db.execute(stmt)
    assert isinstance(result, CursorResult)
    if result.rowcount != 1:
        db.rollback()
        raise TagConflict(load_tag(db, tag.id))


def split_tag(
    db: Session, tag: Tag, expected_version: int, at_ms: int, user_id: uuid.UUID | None
) -> tuple[Tag, Tag]:
    if not tag.start_ms < at_ms < tag.end_ms:
        raise TagInputError("The split point must be inside the tag.")
    player_ids = [tp.player_id for tp in tag.players]
    _bump(db, tag, expected_version, {"end_ms": at_ms, "updated_by": user_id})
    right = Tag(
        event_id=tag.event_id,
        template_id=tag.template_id,
        code=tag.code,
        start_ms=at_ms,
        end_ms=tag.end_ms if tag.end_ms > at_ms else at_ms,
        descriptors=dict(tag.descriptors),
        note=tag.note,
        source=tag.source,
        version=1,
        created_by=user_id,
        updated_by=user_id,
    )
    # `tag.end_ms` above is the value before the bump because the ORM object is not refreshed.
    db.add(right)
    db.flush()
    _set_players(db, right, player_ids)
    return reload(db, tag.id), reload(db, right.id)


def merge_tags(db: Session, refs: list[TagRef], event: Event, user_id: uuid.UUID | None) -> Tag:
    tags: list[Tag] = []
    for ref in refs:
        tag = load_tag(db, ref.id)
        if tag is None or tag.event_id != event.id:
            raise TagInputError("All tags must exist and belong to this match.")
        if ref.version is not None and tag.version != ref.version:
            raise TagConflict(tag)
        tags.append(tag)
    tags.sort(key=lambda t: (t.start_ms, t.created_at))
    keep, others = tags[0], tags[1:]
    descriptors: dict[str, Any] = dict(keep.descriptors)
    for other in others:
        for key, value in other.descriptors.items():
            descriptors.setdefault(key, value)
    notes = [t.note for t in tags if t.note]
    player_ids = list(dict.fromkeys(tp.player_id for t in tags for tp in t.players))
    _bump(
        db,
        keep,
        keep.version,
        {
            "start_ms": min(t.start_ms for t in tags),
            "end_ms": max(t.end_ms for t in tags),
            "descriptors": descriptors,
            "note": " | ".join(dict.fromkeys(notes)) or None,
            "updated_by": user_id,
        },
    )
    _set_players(db, keep, player_ids)
    for other in others:
        db.execute(delete(Tag).where(Tag.id == other.id))
    return reload(db, keep.id)
