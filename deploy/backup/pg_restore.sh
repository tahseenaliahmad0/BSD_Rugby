#!/usr/bin/env bash
# Restore a dump made by pg_dump.sh into the running postgres container.
#   deploy/backup/pg_restore.sh /srv/backups/rugby/rugby-20261013-021500.dump
# Stop the api and workers first: docker compose stop api worker-cpu worker-gpu
set -euo pipefail
FILE="${1:?dump file}"
cd "$(dirname "$0")/../.."
if [ -f deploy/apptainer/rugby.env ] && command -v apptainer >/dev/null 2>&1; then
  set -a; . deploy/apptainer/rugby.env; set +a
  exec apptainer exec --cleanenv --env "PGPASSWORD=${POSTGRES_PASSWORD:-rugby}" deploy/apptainer/images/postgres.sif \
    pg_restore -h 127.0.0.1 -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-rugby}" -d "${POSTGRES_DB:-rugby}" --clean --if-exists --no-owner < "$FILE"
fi
docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-rugby}" -d "${POSTGRES_DB:-rugby}" --clean --if-exists --no-owner < "$FILE"
echo "restored $FILE; start the app again with: docker compose up -d"
