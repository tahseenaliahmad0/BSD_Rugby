#!/usr/bin/env bash
# Usage: start-worker.sh <queue> [concurrency]
set -euo pipefail
cd "$(dirname "$0")/.."
QUEUE="${1:-cpu}"
CONCURRENCY="${2:-1}"
exec celery -A app.workers.celery_app worker -Q "$QUEUE" --concurrency="$CONCURRENCY" \
  --loglevel="${CELERY_LOG_LEVEL:-info}" --hostname="worker-${QUEUE}@%h"
