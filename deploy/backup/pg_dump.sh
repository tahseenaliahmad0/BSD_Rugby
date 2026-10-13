#!/usr/bin/env bash
# Nightly database dump (Docker; with Apptainer it defers to rugby.sh backup). From cron:
#   15 2 * * * /srv/rugby/app/deploy/backup/pg_dump.sh /srv/backups/rugby
# Keeps the last 30 dumps. Restore with deploy/backup/pg_restore.sh.
set -euo pipefail
DEST="${1:?destination directory}"
cd "$(dirname "$0")/../.."
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$DEST/rugby-$STAMP.dump"
if [ -f deploy/apptainer/rugby.env ] && command -v apptainer >/dev/null 2>&1; then
  exec deploy/apptainer/rugby.sh backup "$DEST"
fi
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-rugby}" -Fc "${POSTGRES_DB:-rugby}" > "$FILE"
echo "wrote $FILE ($(du -h "$FILE" | cut -f1))"
ls -1t "$DEST"/rugby-*.dump | tail -n +31 | xargs -r rm --
