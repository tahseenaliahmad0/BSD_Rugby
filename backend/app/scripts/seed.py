"""Seed a development install: an admin, a demo squad and a demo match with a generated clip.

    python -m app.scripts.seed            # idempotent: safe to run again

The admin email, name and password come from ADMIN_EMAIL, ADMIN_NAME and ADMIN_PASSWORD
(defaults in app.config). The clip is FFmpeg's testsrc pattern, so no real footage is needed.
The transcode runs inline, so the match is playable as soon as the script finishes.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.db import get_sessionmaker
from app.models import (
    Event,
    EventType,
    JobStatus,
    Membership,
    Opponent,
    Player,
    Role,
    Season,
    Squad,
    User,
    Video,
    VideoStatus,
)
from app.services.ffmpeg import generate_test_clip
from app.services.jobs import create_job
from app.services.storage import get_storage
from app.services.templates import ensure_default_templates
from app.services.transcode import transcode

DEMO_SQUAD = "Demo Squad"
DEMO_CLIP_NAME = "demo-match-testsrc.mp4"


def seed(*, clip_duration_s: float = 30.0) -> None:
    settings = get_settings()
    storage = get_storage()
    db = get_sessionmaker()()
    try:
        admin = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
        if admin is None:
            admin = User(
                name=settings.admin_name,
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
                is_superadmin=True,
            )
            db.add(admin)
            db.flush()
            print(f"created admin {admin.email}")
        else:
            print(f"admin {admin.email} already exists")

        squad = db.scalar(select(Squad).where(Squad.name == DEMO_SQUAD))
        if squad is None:
            squad = Squad(name=DEMO_SQUAD)
            db.add(squad)
            db.flush()
            print(f"created squad {squad.name}")
        if not db.scalar(
            select(Membership).where(
                Membership.user_id == admin.id, Membership.squad_id == squad.id
            )
        ):
            db.add(Membership(user_id=admin.id, squad_id=squad.id, role=Role.ADMIN))

        ensure_default_templates(db, squad.id, admin.id)

        today = dt.date.today()
        season_name = (
            f"{today.year}-{str(today.year + 1)[-2:]}"
            if today.month >= 7
            else (f"{today.year - 1}-{str(today.year)[-2:]}")
        )
        season = db.scalar(
            select(Season).where(Season.squad_id == squad.id, Season.name == season_name)
        )
        if season is None:
            season = Season(squad_id=squad.id, name=season_name)
            db.add(season)
            db.flush()

        opponent = db.scalar(
            select(Opponent).where(Opponent.squad_id == squad.id, Opponent.name == "Demo Opponents")
        )
        if opponent is None:
            opponent = Opponent(squad_id=squad.id, name="Demo Opponents", primary_colour="#1d4ed8")
            db.add(opponent)
            db.flush()

        if not db.scalar(select(Player).where(Player.squad_id == squad.id)):
            for number, name, position in (
                (1, "A. Prop", "Loosehead"),
                (2, "B. Hooker", "Hooker"),
                (9, "C. Half", "Scrum-half"),
                (10, "D. Fly", "Fly-half"),
                (15, "E. Back", "Full-back"),
            ):
                db.add(
                    Player(
                        squad_id=squad.id,
                        season_id=season.id,
                        name=name,
                        shirt_number=number,
                        position=position,
                    )
                )

        event = db.scalar(
            select(Event).where(Event.squad_id == squad.id, Event.title == "Demo match")
        )
        if event is None:
            event = Event(
                squad_id=squad.id,
                season_id=season.id,
                opponent_id=opponent.id,
                type=EventType.MATCH,
                title="Demo match",
                date=today,
                venue="Home ground",
                competition="Friendly",
                is_home=True,
                created_by=admin.id,
            )
            db.add(event)
            db.flush()
            print("created demo match")

        video = db.scalar(select(Video).where(Video.event_id == event.id))
        if video is not None and video.status == VideoStatus.READY:
            print("demo video already transcoded; nothing to do")
            db.commit()
            return

        if video is None:
            video = Video(
                event_id=event.id,
                camera_label="Main",
                original_filename=DEMO_CLIP_NAME,
                original_path="",
                original_size_bytes=0,
                status=VideoStatus.QUEUED,
                uploaded_by=admin.id,
            )
            db.add(video)
            db.flush()
        original: Path = storage.originals_dir(video.id) / DEMO_CLIP_NAME
        if not original.exists():
            print(f"generating a {clip_duration_s:.0f} s test clip with ffmpeg testsrc ...")
            generate_test_clip(original, settings, duration_s=clip_duration_s)
        video.original_path = storage.relpath(original)
        video.original_size_bytes = original.stat().st_size

        job = create_job(
            db,
            type_="transcode",
            queue="cpu",
            squad_id=squad.id,
            video_id=video.id,
            created_by=admin.id,
            input_={"video_id": str(video.id), "original": video.original_path, "seed": True},
        )
        db.commit()
        print("transcoding the demo clip ...")
        transcode(db, job, video, storage, settings)
        db.refresh(job)
        assert job.status == JobStatus.SUCCEEDED, job.error
        fps = f"{video.fps_num}/{video.fps_den}"
        print(
            f"done. Sign in as {admin.email} and open the squad '{squad.name}' "
            f"to watch the demo match ({video.duration_s:.1f} s at {fps} fps)."
        )
    finally:
        db.close()


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    seed(clip_duration_s=duration)
    return 0


if __name__ == "__main__":
    sys.exit(main())
