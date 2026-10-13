# 0002. Permissive licences only, and what that rules out

Status: accepted. Date: 2026-10-13.

## Context

The college wants no copyleft obligations. The spec rules out Ultralytics
(AGPL). Some popular infrastructure pieces are not permissive either.

## Decision

- Application dependencies must be Apache-2.0, MIT, BSD, ISC or similar.
  `docs/licenses.md` lists every direct dependency with its licence.
- Postgres driver: `psycopg` (v2 and v3) is LGPL-3.0, so the API uses
  `pg8000` (BSD-3, pure Python). It is slower per query but the app is
  small-scale. Switching to psycopg is one dependency and one URL scheme.
- Redis: versions after 7.2 moved to RSALv2/SSPL and then AGPL-or-RSAL. The
  stack pins `redis:7.2` (BSD-3). Valkey (BSD-3) is a drop-in replacement.
- FFmpeg is called as a separate process, never linked. The Debian build
  includes GPL components (libx264); running a GPL tool as a subprocess does
  not make this project a derived work. This is listed in `docs/licenses.md`.

## Consequences

A dependency review is part of adding any package. Model choices in later
milestones follow the same rule (RF-DETR Apache-2.0 sizes only, Qwen3-VL
Apache-2.0).
