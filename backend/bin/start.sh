#!/usr/bin/env bash
# One entry point for every role the backend image plays:
#   start.sh api | worker-cpu | worker-gpu
# Used by the Docker image (CMD) and by the Apptainer %startscript.
set -euo pipefail
cd "$(dirname "$0")/.."
ROLE="${1:-api}"
case "$ROLE" in
  api) exec bin/start-api.sh ;;
  worker-cpu) exec bin/start-worker.sh cpu "${WORKER_CONCURRENCY:-1}" ;;
  worker-gpu) exec bin/start-worker.sh gpu 1 ;;
  *) echo "unknown role '$ROLE' (api | worker-cpu | worker-gpu)" >&2; exit 2 ;;
esac
