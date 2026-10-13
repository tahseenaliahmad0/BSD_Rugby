# Status: Milestones 0 and 1

Date: 2026-10-13. Branch `claude/keen-hawking-km90vd`. Companion to `plan-m0-m1.md`.

## What works

- Sign in with a local account (Argon2id, HTTP-only session cookie, CSRF token), sign out.
- Squad switcher, season and type filters, text search, match list with video counts.
- Create a match or training session (opponent is created on the fly if new).
- Resumable upload of any size over tus with progress, speed, pause, resume and cancel; an
  interrupted upload resumes from the server offset.
- Background transcode on the `cpu` Celery queue: ffprobe, H.264/AAC proxy (constant frame
  rate, keyframe every second, faststart, 1080p cap), poster, thumbnails with a WebVTT index.
  Progress and logs in the jobs table and the API; the match page polls and shows them.
- Player: frame-accurate time from `requestVideoFrameCallback`, frame stepping from the exact
  frame rate, 0.25x to 2x, J/K/L, arrows, Shift+arrows, Home/End, F, M, seek bar with
  thumbnail preview, shortcut tooltips and a shortcut list.
- Video served with HTTP range requests, only to members of the video's squad (Caddy
  `forward_auth` in production, the API itself in development).
- Seed script (admin, demo squad, demo match from an FFmpeg test clip) and a create-admin script.
- Full data model for later milestones in one migration, verified with upgrade, downgrade and
  `alembic check`.

## How it was verified

From a fresh clone on Linux (Python 3.12, Node 22, FFmpeg 6.1, Postgres 16, Redis 7.0):

| Gate | Result |
| --- | --- |
| `make check` (ruff, ruff format, mypy strict, eslint, tsc) | clean |
| `make test` | 18 pytest (auth, CSRF, permissions, tus upload to transcode, media access) and 24 vitest (frame and time maths) pass |
| `make e2e` | 2 Playwright tests pass: login, create match, upload, transcode, player state, speed keys, logout; wrong password message |
| Real footage | the four attached Hudl clips (1280x720, 30 fps) transcode at 3 to 4x realtime on 4 CPU cores with libx264 `veryfast`; proxies keep 30/1 fps, audio, faststart, and a keyframe every 1.000 s |
| Playback in a browser engine | Playwright's Chromium cannot decode H.264, so the demo proxy was re-encoded as VP9 for a one-off check: play and pause, readout matching the displayed frame, single and burst frame steps landing on frames 1, 2, 3, 2, 1, 2 and 12 with `currentTime` at frame centres, Shift+arrow, End, J/K/arrow speed changes |
| Compose files | `docker compose config` valid for the development stack and the production overlay |

Not verified here, and why:

- Docker images and the Caddy configuration: this sandbox has no Docker daemon and outbound
  downloads of the Caddy binary were blocked. CI builds both images and runs `caddy validate`
  on the Caddyfile. Run `docker compose up --build` on a laptop before relying on it.
- Safari: no Mac available. The player uses only standard APIs (`requestVideoFrameCallback`
  is in Safari 15.4+); please check playback, frame stepping and 0.25x speed in Safari during
  the coach review. Chrome: CI runs the smoke test in Google Chrome with H.264.
- NVENC: no GPU here. The encoder is chosen at run time; `TRANSCODE_ENCODER=libx264` forces
  software encoding if NVENC misbehaves.

## What is left (in or near this milestone's scope)

- No UI yet for creating squads, adding members or managing users; the site administrator
  does this through the API (`/api/docs`). Planned for the admin pages in Milestone 2.
- No jobs page; progress shows per video only. The API already lists a squad's jobs.
- Expired tus uploads are marked expired on touch but their `.part` files are not swept
  automatically. A periodic cleanup task is a small addition.
- Ingest from a watched server folder (spec V1) is not started.
- No login rate limiting, no structured log files, no disk-usage page.
- The `worker-gpu` service only consumes an empty queue until Milestone 4.

## Spec changes to consider

1. **Playback direction.** The spec's J/K/L implies Sportscode-style shuttle. Browsers cannot
   play backwards, so J is "slower" here. Suggest the spec says so, or adds "reverse play is
   out of scope for the web player".
2. **Proxy format.** Add that proxies are constant frame rate at the source rate, capped at
   1080p, and that the exact frame rate is stored as a rational. 4K originals are kept but
   played at 1080p.
3. **Licence policy detail.** The spec's "permissive only" rule rules out `psycopg` (LGPL) and
   Redis after 7.2. Suggest naming `pg8000` (or accepting LGPL for drivers) and "Redis 7.2 or
   Valkey".
4. **tus server.** The spec lists tusd or a Python server; this build uses the API. Suggest
   removing the optional `tusd` Compose service from the spec.
5. **Video access control.** State the mechanism (Caddy `forward_auth` on `/media/*`) so
   nginx is not assumed later; it also makes the per-request authorisation cost explicit.
6. **Roster per season.** The Player entity says "per squad and season"; this build uses an
   optional season on each player. If players should carry across seasons with per-season
   shirt numbers, the spec should say so and a `player_seasons` table should be added in
   Milestone 2 before import work depends on it.
7. **Browser verification.** Add a short manual Safari checklist to each milestone review
   (CI covers Chrome).
