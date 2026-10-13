#!/usr/bin/env bash
# Apply migrations, then serve the API. Upgrades are "pull and restart": migrations run here.
# API_HOST / API_PORT default to 0.0.0.0:8000 (Docker); the Apptainer launcher binds 127.0.0.1.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "applying database migrations"
alembic upgrade head
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips='*'
