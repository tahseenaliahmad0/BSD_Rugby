# BSD Rugby video analysis

Self-hosted video analysis for the rugby programme: upload match footage, watch it frame by
frame, tag it, find clips, build playlists and (in later milestones) let AI propose tags. Runs
on the college GPU server with Apptainer (Docker Compose for laptops and CI) and is used
through a browser on the campus network.

Milestones 0 to 2 are done: sign in, pick a squad, create a match, upload a full-length
video (resumable), have it transcoded, watch it frame by frame, tag it with the keyboard, fix
tags on a timeline, find clips across matches, build and share playlists, read stats and
export MP4s. See `docs/SPEC.md` (the spec), `docs/plan-m0-m1.md` and `docs/plan-m2.md` for
the plans, `docs/decisions/` for the decisions behind them, and `docs/guides/` for the
coach guides.

## What is in the repository

| Folder | Contents |
| --- | --- |
| `frontend/` | React + TypeScript app (Vite, Mantine, TanStack Query), Vitest unit tests, Playwright smoke test |
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations, Celery workers, seed scripts, pytest |
| `ml/` | Placeholder for the AI milestones |
| `deploy/` | Caddyfile, Apptainer definition files and launcher, Compose overlay, backup scripts |
| `docs/` | Plan, decision records, licence list |

## Run it with Docker on a laptop (no GPU needed)

Requirements: Docker Desktop (Mac or Windows) or Docker Engine with the Compose plugin.

```bash
git clone <this repository> rugby && cd rugby
docker compose up --build -d
docker compose exec api python -m app.scripts.seed      # admin, demo squad, demo match
```

Open <https://localhost>. The development stack uses Caddy's own certificate, so the browser
warns once; accept it (or run `docker compose exec caddy caddy trust` on Linux). Sign in as
`admin@example.com` with password `change-me-now`, open **Demo Squad** and play the demo match.

Services: `caddy` (HTTPS, frontend, API proxy, video files), `api`, `worker-cpu`
(transcodes), `worker-gpu` (stub for AI jobs), `postgres`, `redis`. Media lives in the
`media` volume, the database in `pgdata`.

## Develop without Docker

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22, FFmpeg, PostgreSQL
16 and Redis running locally (databases `rugby`, `rugby_test` and `rugby_e2e` owned by user
`rugby` / password `rugby`, or set `DATABASE_URL`, `TEST_DATABASE_URL`, `E2E_DATABASE_URL`).

```bash
make setup                 # backend .venv and frontend node_modules
cp backend/.env.example backend/.env
make seed                  # migrations + admin + demo squad + demo match with a generated clip
make dev-api               # http://localhost:8000  (API docs at /api/docs)
make dev-worker            # Celery worker for the cpu queue (transcodes)
make dev-frontend          # http://localhost:5173, proxies /api and /media to the API
```

Checks and tests:

```bash
make check                 # ruff, ruff format, mypy, eslint, tsc
make test                  # pytest (API: auth, permissions, upload to transcode) and vitest
make e2e                   # Playwright: login -> create match -> upload -> play
```

`make e2e` starts its own API on the `rugby_e2e` database and the Vite dev server. Playwright's
own Chromium cannot decode H.264, so install Google Chrome for it (`npx playwright install chrome`
in `frontend/`) and run with `PLAYWRIGHT_CHANNEL=chrome` to exercise playback and frame
stepping; with plain Chromium those two checks are skipped and reported as such.
`PLAYWRIGHT_CHROMIUM_PATH` points Playwright at an existing Chromium binary if needed.

## Production deployment (college server, Apptainer)

The college server runs Apptainer, not Docker. The full procedure is in
`deploy/apptainer/README.md`; in short:

```bash
cd ~ && git clone <this repository> rugby-app && cd ~/rugby-app   # no root needed: everything lives in your home
cp deploy/apptainer/rugby.env.example deploy/apptainer/rugby.env   # edit: DATA_DIR, SITE_ADDRESS, passwords
deploy/apptainer/rugby.sh build      # four .sif images (backend, caddy, postgres, redis)
deploy/apptainer/rugby.sh start      # six instances on the host network
deploy/apptainer/rugby.sh create-admin
```

Open `https://<SITE_ADDRESS>:8443` (a rootless process cannot use 443; IT can change that).
Upgrades are `git pull`, `rugby.sh build`, `rugby.sh restart`; migrations run when the API
starts. `rugby.sh backup <dir>` dumps the database; a user systemd unit restarts everything
after a reboot. The GPU is used automatically when `nvidia-smi` is present. See ADR 0009.

### Docker alternative

On a server with Docker and the NVIDIA Container Toolkit the Compose files work as before:
copy `deploy/.env.production.example` to `.env`, put the certificate in `CERTS_DIR`, then

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
docker compose exec api python -m app.scripts.create_admin --email you@college.edu --name "Your Name"
```

Backups: `deploy/backup/pg_dump.sh` and `pg_restore.sh`.

## How the pieces fit

- **Auth**: local accounts, Argon2id hashes, an HTTP-only `SameSite=Lax` session cookie backed
  by a `sessions` table, and a double-submit CSRF token (`rugby_csrf` cookie, `X-CSRF-Token`
  header) on every state-changing request.
- **Permissions**: a user belongs to squads with a role (`admin`, `analyst`, `coach`,
  `player`). Admins and analysts create matches and upload; coaches watch. Non-members get 404
  so squads are not discoverable. A site administrator (`is_superadmin`) is an admin everywhere.
- **Uploads**: tus 1.0.0 resumable uploads at `/api/uploads`, multi-GB, resumed by the browser
  after a network drop. On completion the file is moved (never copied or re-encoded) to
  `originals/<video id>/` and a transcode job is queued.
- **Transcode** (`worker-cpu`): `ffprobe` for frame rate and duration, then an H.264/AAC MP4
  proxy with the index at the front, a keyframe at least every second, constant frame rate and a
  1080p cap, plus a poster and thumbnails. Job progress is in the `jobs` table and the API.
- **Playback**: Caddy serves `/media/*` with HTTP range requests after asking the API
  (`forward_auth`) whether the signed-in user may see that video. The player uses
  `requestVideoFrameCallback` for the time readout and steps frames using the exact frame rate.
- **Data model**: tags live on the event's timeline; each video carries an offset onto it. All
  tables for later milestones (tags, suggestions, playlists, live sessions, imports) exist now.

## Tagging, clips, playlists, stats and exports (Milestone 2)

- **Templates** (analysts): the code window definition per squad. Buttons have a code, label,
  hotkey, colour, type (instant with lead/lag, or start/stop) and descriptor groups. Saving
  makes a new version; tags remember the version they were made with. New squads get the
  rugby union 15s and sevens defaults.
- **Tagging workspace** (`Tag this match` on a match page): hotkeys create tags at the
  frame-snapped playhead, Shift+letter sets descriptors on the latest or selected tag, the
  canvas timeline supports drag, trim, split, merge, multi-select and undo/redo. Every change
  saves immediately; a concurrent edit of the same tag is reported, never silently overwritten
  (ADRs 0006 to 0008). See `docs/guides/tagging-a-match.md`.
- **Find clips** (coaches): plain-language chips, roster and match filters, saved searches,
  thumbnails, watch a clip, add to a playlist. The search runs server-side on the JSONB
  descriptors and their GIN index. See `docs/guides/finding-clips.md`.
- **Playlists**: from a search (with refresh), hand-picked or ad-hoc ranges; continuous
  playback with next/previous; drag reorder; notes; share with squad staff; duplicate.
- **Stats**: per match or season, success rates from the template's outcome group, per-player
  table, CSV, and every number opens as a playlist.
- **Exports**: a clip or playlist rendered to one MP4 by `worker-cpu` from the originals
  (proxy fallback), optional caption overlay, listed under Downloads.

## Keyboard shortcuts in the player

| Keys | Action |
| --- | --- |
| Space or K | Play / pause |
| L / J | Play faster (to 2x) / slower (to 0.25x) |
| → / ← (or . / ,) | Next / previous frame |
| Shift + → / ← | Forward / back 5 seconds |
| ↑ / ↓ | Speed up / slow down |
| Home / End | Start / end |
| F, M | Full screen, mute |
