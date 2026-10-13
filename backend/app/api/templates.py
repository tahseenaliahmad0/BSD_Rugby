from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.permissions import check_squad_role, require_squad
from app.db import get_db
from app.models import Role, Squad, TagTemplate, User
from app.schemas.templates import TemplateContent, TemplateOut, TemplateSummary, hotkey_clashes
from app.services import templates as svc

router = APIRouter(tags=["templates"])


def _out(template: TagTemplate) -> TemplateOut:
    return TemplateOut.model_validate(template)


def _summary(template: TagTemplate) -> TemplateSummary:
    return TemplateSummary(
        id=template.id,
        family_id=template.family_id,
        name=template.name,
        version=template.version,
        is_active=template.is_active,
        button_count=len(template.buttons),
        created_at=template.created_at,
    )


def _load(db: Session, template_id: uuid.UUID, user: User, minimum: Role) -> TagTemplate:
    template = db.get(TagTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    check_squad_role(db, user, template.squad_id, minimum)
    return template


@router.get("/squads/{squad_id}/templates", response_model=list[TemplateOut])
def list_templates(
    squad: Squad = Depends(require_squad(Role.PLAYER)), db: Session = Depends(get_db)
) -> list[TemplateOut]:
    return [_out(t) for t in svc.active_templates(db, squad.id)]


@router.post(
    "/squads/{squad_id}/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED
)
def create_template(
    body: TemplateContent,
    squad: Squad = Depends(require_squad(Role.ANALYST)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateOut:
    template = svc.create_template(db, squad.id, body, user.id)
    db.commit()
    return _out(template)


@router.post("/squads/{squad_id}/templates/defaults", response_model=list[TemplateOut])
def create_default_templates(
    squad: Squad = Depends(require_squad(Role.ANALYST)),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TemplateOut]:
    created = svc.ensure_default_templates(db, squad.id, user.id)
    db.commit()
    return [_out(t) for t in created]


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str]
    clashes: list[str]


@router.post("/squads/{squad_id}/templates/validate", response_model=ValidationResult)
def validate_template(
    body: dict[str, object],
    squad: Squad = Depends(require_squad(Role.ANALYST)),
) -> ValidationResult:
    """Check a draft without saving it, so the editor can show problems as the analyst types."""
    try:
        content = TemplateContent.model_validate(body)
    except ValidationError as exc:
        errors = [e["msg"].removeprefix("Value error, ") for e in exc.errors()]
        return ValidationResult(ok=False, errors=errors, clashes=[])
    clashes = hotkey_clashes(content)
    return ValidationResult(ok=not clashes, errors=[], clashes=clashes)


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateOut:
    return _out(_load(db, template_id, user, Role.PLAYER))


@router.put(
    "/templates/{template_id}", response_model=TemplateOut, status_code=status.HTTP_201_CREATED
)
def save_new_version(
    template_id: uuid.UUID,
    body: TemplateContent,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateOut:
    """Editing never changes a stored version: it creates the next one and activates it."""
    current = _load(db, template_id, user, Role.ANALYST)
    template = svc.new_version(db, current, body, user.id)
    db.commit()
    return _out(template)


@router.get("/templates/{template_id}/versions", response_model=list[TemplateSummary])
def list_versions(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TemplateSummary]:
    template = _load(db, template_id, user, Role.PLAYER)
    return [_summary(t) for t in svc.family_versions(db, template.family_id)]


@router.post("/templates/{template_id}/activate", response_model=TemplateOut)
def activate_version(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateOut:
    template = _load(db, template_id, user, Role.ANALYST)
    svc.activate_version(db, template)
    db.commit()
    return _out(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def retire_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Retire a whole family. Versions stay so old tags keep their definition."""
    template = _load(db, template_id, user, Role.ADMIN)
    svc.deactivate_family(db, template.family_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
