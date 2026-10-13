from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.permissions import require_squad
from app.db import get_db
from app.models import Event, Role, Squad
from app.schemas.stats import StatsOut
from app.services import stats as svc

router = APIRouter(tags=["stats"])


@router.get("/squads/{squad_id}/stats", response_model=StatsOut)
def get_stats(
    squad: Squad = Depends(require_squad(Role.PLAYER)),
    db: Session = Depends(get_db),
    event_id: uuid.UUID | None = None,
    season_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    format: Literal["json", "csv"] = "json",
    table: Literal["codes", "players"] = Query(default="codes"),
) -> StatsOut | Response:
    if event_id is not None:
        event = db.get(Event, event_id)
        if event is None or event.squad_id != squad.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    template = svc.pick_template(db, squad.id, template_id)
    stats = svc.compute_stats(
        db, squad.id, event_id=event_id, season_id=season_id, template=template
    )
    if format == "json":
        return stats
    body = svc.codes_csv(stats) if table == "codes" else svc.players_csv(stats)
    filename = f"stats-{table}.csv"
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
