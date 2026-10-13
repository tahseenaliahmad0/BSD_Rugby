#!/usr/bin/env bash
# Restore a dump made by pg_dump.sh into the running postgres container.
#   deploy/backup/pg_restore.sh /srv/backups/rugby/rugby-20261013-021500.dump
# Stop the api and workers first: docker compose stop api worker-cpu worker-gpu
set -euo pipefail
FILE="${1:?dump file}"
cd "$(dirname "$0")/../.."
docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-rugby}" -d "${POSTGRES_DB:-rugby}" --clean --if-exists --no-owner < "$FILE"
echo "restored $FILE; start the app again with: docker compose up -d"
