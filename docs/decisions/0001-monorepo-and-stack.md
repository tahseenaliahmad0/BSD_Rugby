# 0001. Monorepo and stack versions

Status: accepted. Date: 2026-10-13.

## Context

The spec fixes the stack: React + TypeScript + Vite frontend, FastAPI +
SQLAlchemy 2 + Alembic + PostgreSQL backend, Celery + Redis workers, FFmpeg,
Caddy, all in Docker Compose. It also asks for a layout of `frontend/`,
`backend/`, `ml/`, `deploy/` and `docs/`.

## Decision

- One Git repository with that layout. The backend package also contains the
  Celery workers and the scripts, so one Docker image serves `api`,
  `worker-cpu` and `worker-gpu`.
- Python 3.12, managed with `uv` and a `pyproject.toml`; `ruff` for lint and
  format, `mypy` for types, `pytest` for tests.
- Node 22 and npm with a lockfile; Vite 7, React 19, TypeScript 5.9, ESLint 9,
  Vitest 3, Playwright. Newer majors (Vite 8, TypeScript 7) exist but are too
  fresh for a project meant to be maintained by students; pins are reviewed per
  milestone.
- Mantine for UI components because it ships large, accessible controls that
  suit a coach-facing interface. TanStack Query for server state.
- `make check` is the single lint and type gate; CI runs it.

## Consequences

Contributors need `uv`, Node 22, FFmpeg, Postgres and Redis locally, or they
use the Compose stack. The ML package stays empty until Milestone 4.
