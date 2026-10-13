"""Counts and success rates from tags, per code and per player, with a filter for each number.

Success is defined by the squad's active template: the outcome descriptor group and which of
its values count as success. A tag without an outcome value counts in `count` but not in the
success rate. Each row carries the filter that reproduces its clips, so a number can be opened
as a playlist.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Event, Player, Tag, TagTemplate
from app.schemas.clips import FilterDefinition
from app.schemas.stats import CodeStat, PlayerStat, StatsOut
from app.services.templates import active_templates


@dataclass
class _Acc:
    count: int = 0
    with_outcome: int = 0
    successes: int = 0
    by_code: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def _rate(acc: _Acc) -> float | None:
    return acc.successes / acc.with_outcome if acc.with_outcome else None


def _outcome_values(tag: Tag, group: str | None) -> list[str]:
    if group is None:
        return []
    raw = tag.descriptors.get(group)
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [v for v in raw if isinstance(v, str)]
    return []


def pick_template(
    db: Session, squad_id: uuid.UUID, template_id: uuid.UUID | None
) -> TagTemplate | None:
    if template_id is not None:
        template = db.get(TagTemplate, template_id)
        if template is not None and template.squad_id == squad_id:
            return template
    templates = active_templates(db, squad_id)
    return templates[0] if templates else None


def compute_stats(
    db: Session,
    squad_id: uuid.UUID,
    *,
    event_id: uuid.UUID | None,
    season_id: uuid.UUID | None,
    template: TagTemplate | None,
) -> StatsOut:
    query = (
        select(Tag)
        .join(Event, Tag.event_id == Event.id)
        .where(Event.squad_id == squad_id)
        .options(selectinload(Tag.players))
    )
    if event_id is not None:
        query = query.where(Tag.event_id == event_id)
    if season_id is not None:
        query = query.where(Event.season_id == season_id)
    tags = list(db.scalars(query))

    outcome_group = template.outcome_group if template else None
    success_values = list(template.success_values) if template else []
    button_info = {b["code"]: b for b in (template.buttons if template else [])}
    code_order = [b["code"] for b in (template.buttons if template else [])]
    outcome_options: list[str] = []
    if template and outcome_group:
        for group in template.descriptor_groups:
            if group["key"] == outcome_group:
                outcome_options = [o["value"] for o in group.get("options", [])]
    failure_values = [v for v in outcome_options if v not in success_values]

    codes: dict[str, _Acc] = defaultdict(_Acc)
    players: dict[uuid.UUID, _Acc] = defaultdict(_Acc)
    for tag in tags:
        values = _outcome_values(tag, outcome_group)
        has_outcome = bool(values)
        success = has_outcome and any(v in success_values for v in values)
        for acc in [codes[tag.code]] + [players[tp.player_id] for tp in tag.players]:
            acc.count += 1
            acc.by_code[tag.code] += 1
            if has_outcome:
                acc.with_outcome += 1
                if success:
                    acc.successes += 1

    scope = FilterDefinition(
        event_ids=[event_id] if event_id else [], season_ids=[season_id] if season_id else []
    )

    def scoped(**changes: object) -> FilterDefinition:
        return scope.model_copy(update=changes)

    ordered_codes = [c for c in code_order if c in codes] + sorted(
        c for c in codes if c not in code_order
    )
    code_rows = [
        CodeStat(
            code=code,
            label=button_info.get(code, {}).get("label") or code,
            colour=button_info.get(code, {}).get("colour"),
            count=codes[code].count,
            with_outcome=codes[code].with_outcome,
            successes=codes[code].successes,
            success_rate=_rate(codes[code]),
            filter=scoped(codes=[code]),
            success_filter=scoped(codes=[code], descriptors={outcome_group: success_values})
            if outcome_group and success_values
            else None,
            failure_filter=scoped(codes=[code], descriptors={outcome_group: failure_values})
            if outcome_group and failure_values
            else None,
        )
        for code in ordered_codes
    ]

    roster = (
        {p.id: p for p in db.scalars(select(Player).where(Player.id.in_(list(players)))).all()}
        if players
        else {}
    )
    player_rows = sorted(
        (
            PlayerStat(
                player_id=pid,
                name=roster[pid].name,
                shirt_number=roster[pid].shirt_number,
                total=acc.count,
                by_code=dict(acc.by_code),
                with_outcome=acc.with_outcome,
                successes=acc.successes,
                success_rate=_rate(acc),
                filter=scoped(player_ids=[pid]),
            )
            for pid, acc in players.items()
            if pid in roster
        ),
        key=lambda r: (r.shirt_number is None, r.shirt_number or 0, r.name),
    )
    return StatsOut(
        event_id=event_id,
        season_id=season_id,
        template_name=template.name if template else None,
        outcome_group=outcome_group,
        success_values=success_values,
        tag_count=len(tags),
        codes=code_rows,
        code_order=ordered_codes,
        players=player_rows,
    )


def _pct(rate: float | None) -> str:
    return "" if rate is None else f"{rate * 100:.1f}%"


def codes_csv(stats: StatsOut) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["code", "count", "with_outcome", "successes", "success_rate"])
    for row in stats.codes:
        writer.writerow(
            [row.label, row.count, row.with_outcome, row.successes, _pct(row.success_rate)]
        )
    return out.getvalue()


def players_csv(stats: StatsOut) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["player", "shirt", "total", *stats.code_order, "with_outcome", "successes", "success_rate"]
    )
    for row in stats.players:
        writer.writerow(
            [
                row.name,
                row.shirt_number if row.shirt_number is not None else "",
                row.total,
                *[row.by_code.get(code, 0) for code in stats.code_order],
                row.with_outcome,
                row.successes,
                _pct(row.success_rate),
            ]
        )
    return out.getvalue()
