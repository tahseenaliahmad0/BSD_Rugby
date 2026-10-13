# 0004. Serving video through Caddy with per-squad access control

Status: accepted. Date: 2026-10-13.

## Context

Seeking needs HTTP range requests served by a real file server, but users may
only see videos from squads they belong to. Caddy has no X-Sendfile.

## Decision

- All media lives under `STORAGE_ROOT` and is addressed as
  `/media/proxies/<video id>/proxy.mp4`, `/media/proxies/<video id>/poster.jpg`,
  `/media/proxies/<video id>/thumbs/<n>.jpg` and
  `/media/originals/<video id>/<file>`.
- In production Caddy handles `/media/*` with `forward_auth` to
  `GET /api/media/authorize`. The API reads the original URI, resolves the
  video id, checks the session's squad membership, and answers 204 or 401/403.
  Caddy then serves the file with `file_server`, which supports byte ranges.
- In development, with no Caddy in front, the API serves `/media/*` itself
  using Starlette's range-capable `FileResponse` after the same check.
- Uploads in progress (`uploads/`) are never served.

## Consequences

Every range request costs one small authorisation call (session and video
lookups). That is fine for a campus deployment; a short in-memory cache can be
added if it ever shows up in profiles.
