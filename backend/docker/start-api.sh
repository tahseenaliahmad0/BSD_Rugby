#!/usr/bin/env bash
# Apply migrations, then serve the API. Upgrades are "pull and restart": migrations run here.
set -euo pipefail
cd /app
echo "applying database migrations"
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
