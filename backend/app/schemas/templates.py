"""Tag template content: the code window definition, validated before it is stored as JSON."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel

# Keys the player owns in the tagging workspace (both cases). A template may not use them.
RESERVED_HOTKEYS: frozenset[str] = frozenset(
    {" ", ",", ".", "j", "k", "l", "f", "m", "J", "K", "L", "F", "M"}
)
_KEY_RE = re.compile(r"^[A-Za-z0-9!@#$%^&*()\-_=+\[\]{};:'\"<>?/\\|`~]$")
_SLUG_RE = re.compile(r"^[a-z0-9_]{1,50}$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_hotkey(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not _KEY_RE.match(value):
        raise ValueError(f"Hotkey {value!r} must be a single letter, digit or symbol.")
    if value in RESERVED_HOTKEYS:
        raise ValueError(
            f"Hotkey {value!r} is used by the video player "
            "(Space, J, K, L, F, M, comma, full stop)."
        )
    return value


class DescriptorOption(BaseModel):
    value: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=50)
    hotkey: str | None = None

    _check_hotkey = field_validator("hotkey")(validate_hotkey)


class DescriptorGroup(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=50)
    kind: Literal["options", "players"] = "options"
    multiple: bool = False
    options: list[DescriptorOption] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not _SLUG_RE.match(value):
            raise ValueError("Group keys use lower-case letters, digits and underscores.")
        return value

    @model_validator(mode="after")
    def _unique_options(self) -> DescriptorGroup:
        values = [o.value.lower() for o in self.options]
        if len(values) != len(set(values)):
            raise ValueError(f"Group '{self.label}' has duplicate options.")
        if self.kind == "players" and self.options:
            raise ValueError("A players group takes its options from the roster, not the template.")
        return self


class TemplateButton(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, max_length=100)
    hotkey: str | None = None
    colour: str = "#2f9e44"
    kind: Literal["instant", "span"] = "instant"
    lead_ms: int = Field(default=3000, ge=0, le=120_000)
    lag_ms: int = Field(default=3000, ge=0, le=120_000)
    groups: list[str] = Field(default_factory=list)

    _check_hotkey = field_validator("hotkey")(validate_hotkey)

    @field_validator("colour")
    @classmethod
    def _hex(cls, value: str) -> str:
        if not _HEX_RE.match(value):
            raise ValueError("Colours are hex like #2f9e44.")
        return value.lower()


class TemplateContent(BaseModel):
    """What the editor saves. Every save becomes a new version of the template family."""

    name: str = Field(min_length=1, max_length=100)
    buttons: list[TemplateButton] = Field(default_factory=list)
    descriptor_groups: list[DescriptorGroup] = Field(default_factory=list)
    outcome_group: str | None = None
    success_values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> TemplateContent:
        codes = [b.code.strip().lower() for b in self.buttons]
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        if dupes:
            raise ValueError(f"Duplicate codes: {', '.join(dupes)}.")
        group_keys = [g.key for g in self.descriptor_groups]
        if len(group_keys) != len(set(group_keys)):
            raise ValueError("Duplicate descriptor group keys.")
        groups = {g.key: g for g in self.descriptor_groups}
        for button in self.buttons:
            for key in button.groups:
                if key not in groups:
                    raise ValueError(f"Button '{button.code}' uses unknown group '{key}'.")
        clashes = hotkey_clashes(self)
        if clashes:
            raise ValueError("Hotkey clashes: " + "; ".join(clashes))
        if self.outcome_group is not None:
            group = groups.get(self.outcome_group)
            if group is None or group.kind != "options":
                raise ValueError("The outcome group must be one of the option groups.")
            allowed = {o.value for o in group.options}
            bad = [v for v in self.success_values if v not in allowed]
            if bad:
                raise ValueError(f"Success values not in the outcome group: {', '.join(bad)}.")
        elif self.success_values:
            raise ValueError("Choose an outcome group before picking success values.")
        return self


def hotkey_clashes(content: TemplateContent) -> list[str]:
    """Human-readable list of keys used more than once, across buttons and descriptor options."""
    owners: dict[str, list[str]] = {}
    for button in content.buttons:
        if button.hotkey:
            owners.setdefault(button.hotkey, []).append(button.label or button.code)
    for group in content.descriptor_groups:
        for option in group.options:
            if option.hotkey:
                owners.setdefault(option.hotkey, []).append(
                    f"{group.label}: {option.label or option.value}"
                )
    return [
        f"'{key}' is used by {', '.join(names)}" for key, names in owners.items() if len(names) > 1
    ]


class TemplateOut(ORMModel):
    id: uuid.UUID
    squad_id: uuid.UUID
    family_id: uuid.UUID
    name: str
    version: int
    is_active: bool
    buttons: list[TemplateButton]
    descriptor_groups: list[DescriptorGroup]
    outcome_group: str | None
    success_values: list[str]
    created_by: uuid.UUID | None
    created_at: datetime


class TemplateSummary(ORMModel):
    id: uuid.UUID
    family_id: uuid.UUID
    name: str
    version: int
    is_active: bool
    button_count: int
    created_at: datetime
