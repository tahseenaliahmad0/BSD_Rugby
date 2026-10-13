"""Tag template families and versions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import TagTemplate
from app.schemas.templates import TemplateContent
from app.services.default_templates import default_templates


def _apply_content(template: TagTemplate, content: TemplateContent) -> None:
    template.name = content.name
    template.buttons = [b.model_dump() for b in content.buttons]
    template.descriptor_groups = [g.model_dump() for g in content.descriptor_groups]
    template.outcome_group = content.outcome_group
    template.success_values = list(content.success_values)


def create_template(
    db: Session, squad_id: uuid.UUID, content: TemplateContent, user_id: uuid.UUID | None
) -> TagTemplate:
    template = TagTemplate(
        squad_id=squad_id, family_id=uuid.uuid4(), version=1, is_active=True, created_by=user_id
    )
    _apply_content(template, content)
    db.add(template)
    db.flush()
    return template


def new_version(
    db: Session, current: TagTemplate, content: TemplateContent, user_id: uuid.UUID | None
) -> TagTemplate:
    """Save edits as the next version of the family and make it the active one."""
    latest = db.scalar(
        select(func.max(TagTemplate.version)).where(TagTemplate.family_id == current.family_id)
    )
    db.execute(
        update(TagTemplate)
        .where(TagTemplate.family_id == current.family_id)
        .values(is_active=False)
    )
    template = TagTemplate(
        squad_id=current.squad_id,
        family_id=current.family_id,
        version=(latest or 0) + 1,
        is_active=True,
        created_by=user_id,
    )
    _apply_content(template, content)
    db.add(template)
    db.flush()
    return template


def activate_version(db: Session, template: TagTemplate) -> TagTemplate:
    db.execute(
        update(TagTemplate)
        .where(TagTemplate.family_id == template.family_id)
        .values(is_active=False)
    )
    template.is_active = True
    db.flush()
    return template


def deactivate_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(TagTemplate).where(TagTemplate.family_id == family_id).values(is_active=False)
    )


def active_templates(db: Session, squad_id: uuid.UUID) -> list[TagTemplate]:
    return list(
        db.scalars(
            select(TagTemplate)
            .where(TagTemplate.squad_id == squad_id, TagTemplate.is_active.is_(True))
            .order_by(TagTemplate.name)
        )
    )


def family_versions(db: Session, family_id: uuid.UUID) -> list[TagTemplate]:
    return list(
        db.scalars(
            select(TagTemplate)
            .where(TagTemplate.family_id == family_id)
            .order_by(TagTemplate.version.desc())
        )
    )


def ensure_default_templates(
    db: Session, squad_id: uuid.UUID, user_id: uuid.UUID | None
) -> list[TagTemplate]:
    """Create the 15s and sevens templates for a squad that has none yet."""
    existing = db.scalar(
        select(func.count()).select_from(TagTemplate).where(TagTemplate.squad_id == squad_id)
    )
    if existing:
        return active_templates(db, squad_id)
    created = [create_template(db, squad_id, content, user_id) for content in default_templates()]
    return created
