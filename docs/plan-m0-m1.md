# Plan: Milestones 0 and 1 (Foundations, Footage and playback)

Goal: a working vertical slice. Log in, create a squad and a match, upload a
full-length match video, have it transcoded, and watch it in a frame-accurate
player. Tagging, live tagging, Hudl import, AI, playlists and drawings are out
of scope for now, but their tables are created so later milestones need no
schema rewrite.

## Repository layout

```
frontend/   React + TypeScript + Vite + Mantine + TanStack Query; Vitest; Playwright
backend/    FastAPI API, SQLAlchemy 2 models, Alembic migrations, Celery workers, scripts, pytest
ml/         Placeholder for models and training scripts; the gpu worker stub lives in backend
deploy/     Production Compose overlay, Caddyfile, backup script
docs/       This plan, ADRs in docs/decisions/, licence list
docker-compose.yml   Development stack (no GPU needed)
Makefile             make check / make test / make e2e / make seed
```

## Order of work (one commit per step, each step leaves the repo working)

1. Plan, skeleton, Makefile, ADRs for the decisions below.
2. Backend package, settings, database models for every entity in the spec,
   Alembic initial migration. Verified with upgrade and downgrade on Postgres.
3. Auth (Argon2, HTTP-only session cookie, double-submit CSRF), users, squads,
   memberships, players, seasons, opponents, events, videos. Pytest for auth,
   CSRF and squad isolation.
4. Resumable uploads (tus 1.0.0 server inside the API), storage layout,
   Celery app with `cpu` and `gpu` queues, transcode task (ffprobe, H.264/AAC
   proxy with faststart and a keyframe every second, poster, thumbnails,
   progress), jobs API, media access control for Caddy. Pytest for the
   upload-to-transcode path with the Celery task run inline.
5. Seed script (admin, demo squad, demo match, FFmpeg `testsrc` clip) and a
   create-admin script.
6. Frontend: login, squad switcher, library (seasons and matches), create
   match, upload with progress, job status, frame-accurate player. Vitest for
   frame and time maths.
7. Docker: backend image, Caddy image that builds the frontend, dev Compose,
   production overlay with the NVIDIA device reservation, Caddyfile.
8. Playwright smoke test (login, create match, upload, play) and a CI workflow.
9. Clean-checkout verification, README, licence list, final report.

## Key files

- `backend/app/models/*.py` all tables; `backend/alembic/versions/0001_initial.py`
- `backend/app/core/security.py` Argon2 and session tokens; `backend/app/core/csrf.py`
- `backend/app/api/uploads.py` tus server; `backend/app/services/transcode.py` FFmpeg
- `backend/app/workers/celery_app.py`, `backend/app/workers/tasks.py`
- `backend/app/api/media.py` authorisation for Caddy `forward_auth` and dev range serving
- `backend/app/scripts/seed.py`, `backend/app/scripts/create_admin.py`
- `frontend/src/player/frameMath.ts` pure frame and time maths (unit tested)
- `frontend/src/player/VideoPlayer.tsx` the player; `frontend/src/upload/UploadPanel.tsx`
- `deploy/Caddyfile`, `docker-compose.yml`, `deploy/docker-compose.prod.yml`

## Assumptions

- One installation serves one club. A global `is_superadmin` flag on a user
  grants admin on every squad and is how the first admin bootstraps squads.
- Squad roles are `admin`, `analyst`, `coach`, `player`. Admin and analyst can
  create matches and upload; coach can view; player is reserved for later.
- The server has FFmpeg with libx264; NVENC is used when the `h264_nvenc`
  encoder is reported by FFmpeg and `TRANSCODE_ENCODER=auto` (the default).
- Proxies are capped at 1080p and keep the source frame rate, forced to a
  constant frame rate so frame numbers map exactly to time.
- Multi-GB uploads land under `STORAGE_ROOT/uploads` and are moved (same
  filesystem, atomic rename) to `STORAGE_ROOT/originals/<video id>/` once
  complete. The original is never rewritten.
- The campus deployment uses a TLS certificate that college laptops trust;
  the dev stack uses Caddy's internal CA on `https://localhost`.

## Spec ambiguities resolved

| Question | Decision |
| --- | --- |
| tus server: tusd container or Python? | Python tus server inside the API, so one auth and permission system covers uploads and no extra service or hook plumbing is needed. See ADR 0003. |
| How does Caddy enforce per-squad video access? | Caddy `forward_auth` asks the API to authorise each `/media/*` request, then `file_server` serves the file with byte ranges. In dev (no Caddy) the API serves `/media/*` itself with range support. See ADR 0004. |
| Postgres driver licence | `psycopg` is LGPL, so the BSD-licensed pure-Python `pg8000` driver is used. Swap is one setting if LGPL is accepted later. See ADR 0002. |
| Redis licence | Redis changed licence after 7.2; the stack pins `redis:7.2` (BSD-3). Valkey is a drop-in alternative. See ADR 0002. |
| "Player" entity roster per squad and season | `players.season_id` is nullable: a player row belongs to a squad and optionally to one season. |
| Frame rate storage | Stored as an exact rational (`fps_num`/`fps_den`) from the proxy, plus duration and frame count, so 29.97 fps footage steps correctly. |
| Tag times on the event timeline | `tags.start_s`/`end_s` are seconds on the event timeline; `videos.offset_s` is the video's start on that timeline. Video time = event time - offset. |
| J/K/L on the web | Browsers cannot play backwards, so J slows playback (down to 0.25x), K pauses, L plays and speeds up (to 2x). Arrows step one frame; Shift+arrows jump 5 s. |
| Thumbnails format | One JPEG every 10 s of proxy time plus a WebVTT index; the API exposes the interval and count. |
| Upload size limit | No application limit; the disk is the limit. Caddy's request body limit is left unset for `/api/uploads`. |
| Seed clip | `testsrc` 1280x720 at 30 fps for 30 s with a sine tone, burnt-in timestamp from the source itself. |
