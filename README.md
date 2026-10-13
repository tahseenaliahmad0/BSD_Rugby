# BSD Rugby video analysis

Self-hosted video analysis for the rugby programme: upload match footage, watch it frame by
frame, and (in later milestones) tag it, build playlists and let AI propose tags. Runs on the
college GPU server with Docker Compose and is used through a browser on the campus network.

Milestones 0 and 1 are done: sign in, pick a squad, create a match, upload a full-length
video (resumable), have it transcoded in the background, and watch it in a frame-accurate
player. See `docs/plan-m0-m1.md` for the plan and `docs/decisions/` for the decisions behind it.

## What is in the repository

| Folder | Contents |
| --- | --- |
| `frontend/` | React + TypeScript app (Vite, Mantine, TanStack Query), Vitest unit tests, Playwright smoke test |
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations, Celery workers, seed scripts, pytest |
| `ml/` | Placeholder for the AI milestones |
| `deploy/` | Caddyfile, production Compose overlay, backup scripts |
| `docs/` | Plan, decision records, licence list |

## Run it with Docker (any laptop, no GPU needed)

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

`make e2e` starts its own API on the `rugby_e2e` database and the Vite dev server. If
Playwright's bundled Chromium is not installed, run `npx playwright install chromium` in
`frontend/` or point `PLAYWRIGHT_CHROMIUM_PATH` at a Chromium binary.

## Production deployment (college server)

1. Confirm the IT checklist in the design spec: Docker with the NVIDIA Container Toolkit, a
   campus hostname, a TLS certificate that college laptops trust, storage volume and backups.
2. Clone the repository to the server (for example `/srv/rugby/app`) and create the data
   folders: `/srv/rugby/postgres`, `/srv/rugby/media`, `/srv/rugby/certs` (put `fullchain.pem`
   and `privkey.pem` there).
3. `cp deploy/.env.production.example .env` and fill in the hostname, folders and passwords.
4. Start everything:

   ```bash
   docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
   ```

   Migrations run automatically when the `api` container starts.
5. Create the first admin (the seed script is for development only):

   ```bash
   docker compose exec api python -m app.scripts.create_admin --email you@college.edu --name "Your Name"
   ```

   It prompts for a password (or reads `ADMIN_PASSWORD`). This account is a site
   administrator: it can create squads with `POST /api/squads` (see `/api/docs`) and add
   coaches and analysts to them with `POST /api/squads/{id}/members`. A squad admin UI arrives
   with Milestone 2.
6. Upgrades: `git pull`, then the same `up -d --build` command.
7. Backups: `deploy/backup/pg_dump.sh /srv/backups/rugby` from cron nightly; restore with
   `deploy/backup/pg_restore.sh`. Back up `/srv/rugby/media/originals` under IT's storage
   policy; proxies and thumbnails can be regenerated.

Transcodes use NVENC automatically when FFmpeg in the worker can reach the GPU
(`TRANSCODE_ENCODER=auto`); set `TRANSCODE_ENCODER=libx264` to force software encoding.

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
