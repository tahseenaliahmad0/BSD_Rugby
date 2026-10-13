#!/usr/bin/env bash
# Starts the API for the Playwright smoke test on a dedicated database with inline transcoding.
set -euo pipefail
cd "$(dirname "$0")/../../backend"

export APP_ENV=test
export DATABASE_URL="${E2E_DATABASE_URL:-postgresql+pg8000://rugby:rugby@localhost:5432/rugby_e2e}"
export STORAGE_ROOT="${E2E_STORAGE_ROOT:-$(mktemp -d -t rugby-e2e-XXXXXX)}"
export CELERY_TASK_ALWAYS_EAGER=true
export COOKIE_SECURE=false
export TRANSCODE_ENCODER=libx264
export TRANSCODE_PRESET=ultrafast
export THUMBNAIL_INTERVAL_S=2
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=admin-password-123
export ADMIN_NAME="Demo Admin"

uv run alembic downgrade base >/dev/null
uv run alembic upgrade head >/dev/null
uv run python -m app.scripts.seed 3
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning
