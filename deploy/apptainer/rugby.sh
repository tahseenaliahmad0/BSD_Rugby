#!/usr/bin/env bash
# Run the rugby video analysis app with Apptainer (no Docker, no root).
#
#   deploy/apptainer/rugby.sh build          build the four images (needs network; may need --fakeroot)
#   deploy/apptainer/rugby.sh start          start postgres, redis, api, workers, caddy as instances
#   deploy/apptainer/rugby.sh stop | restart | status
#   deploy/apptainer/rugby.sh logs <service> [-f]
#   deploy/apptainer/rugby.sh create-admin   first administrator (prompts for a password)
#   deploy/apptainer/rugby.sh seed           demo squad and match (development only)
#   deploy/apptainer/rugby.sh backup <dir>   pg_dump into <dir>
#   deploy/apptainer/rugby.sh shell <service>
#   deploy/apptainer/rugby.sh install-service   user systemd unit so it restarts after a reboot
#
# Services run on the host network: Postgres, Redis and the API bind 127.0.0.1; Caddy is the only
# public port. Settings come from deploy/apptainer/rugby.env (see rugby.env.example).
# DRY_RUN=1 prints the apptainer commands instead of running them.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
APPTAINER="${APPTAINER:-apptainer}"
ENV_FILE="${RUGBY_ENV:-$HERE/rugby.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

DATA_DIR="${DATA_DIR:-$HOME/rugby-data}"
DATA_DIR="${DATA_DIR/#\~/$HOME}"
IMAGES_DIR="${IMAGES_DIR:-$HERE/images}"
SITE_ADDRESS="${SITE_ADDRESS:-localhost}"
HTTP_PORT="${HTTP_PORT:-8080}"
HTTPS_PORT="${HTTPS_PORT:-8443}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
API_PORT="${API_PORT:-8000}"
POSTGRES_USER="${POSTGRES_USER:-rugby}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-rugby}"
POSTGRES_DB="${POSTGRES_DB:-rugby}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_NAME="${ADMIN_NAME:-Admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-change-me-now}"
TRANSCODE_ENCODER="${TRANSCODE_ENCODER:-auto}"
GPU="${GPU:-auto}"
WORKER_CONCURRENCY="${WORKER_CONCURRENCY:-1}"
CERTS_DIR="${CERTS_DIR:-}"
TLS_FILE="${TLS_FILE:-$HERE/tls.caddy}"
PREFIX="${INSTANCE_PREFIX:-rugby}"

SERVICES=(postgres redis api worker-cpu worker-gpu caddy)

log() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die() { log "error: $*"; exit 1; }

run() {
  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf '+'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

need_apptainer() {
  command -v "$APPTAINER" >/dev/null 2>&1 || die "apptainer not found on PATH"
}

need_image() {
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  [ -f "$IMAGES_DIR/$1.sif" ] || die "missing $IMAGES_DIR/$1.sif (run: rugby.sh build)"
}

gpu_flag() {
  case "$GPU" in
    yes|true|1) echo "--nv" ;;
    no|false|0) echo "" ;;
    *) if command -v nvidia-smi >/dev/null 2>&1; then echo "--nv"; else echo ""; fi ;;
  esac
}

instance_running() {
  [ "${DRY_RUN:-0}" = "1" ] && return 1
  "$APPTAINER" instance list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$PREFIX-$1"
}

backend_env_file() {
  local f="$DATA_DIR/run/backend.env"
  mkdir -p "$DATA_DIR/run"
  cat > "$f" <<ENV
APP_ENV=production
DATABASE_URL=postgresql+pg8000://$POSTGRES_USER:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/$POSTGRES_DB
REDIS_URL=redis://127.0.0.1:$REDIS_PORT/0
STORAGE_ROOT=/data
COOKIE_SECURE=true
API_SERVES_MEDIA=false
API_HOST=127.0.0.1
API_PORT=$API_PORT
TRANSCODE_ENCODER=$TRANSCODE_ENCODER
WORKER_CONCURRENCY=$WORKER_CONCURRENCY
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_NAME=$ADMIN_NAME
ADMIN_PASSWORD=$ADMIN_PASSWORD
ENV
  chmod 600 "$f"
  echo "$f"
}

caddy_env_file() {
  local f="$DATA_DIR/run/caddy.env"
  mkdir -p "$DATA_DIR/run"
  cat > "$f" <<ENV
SITE_ADDRESS=$SITE_ADDRESS
HTTP_PORT=$HTTP_PORT
HTTPS_PORT=$HTTPS_PORT
API_UPSTREAM=127.0.0.1:$API_PORT
MEDIA_ROOT=/srv/media
ENV
  echo "$f"
}

postgres_env_file() {
  local f="$DATA_DIR/run/postgres.env"
  mkdir -p "$DATA_DIR/run"
  cat > "$f" <<ENV
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
PGPORT=$POSTGRES_PORT
ENV
  chmod 600 "$f"
  echo "$f"
}

prepare_dirs() {
  mkdir -p "$DATA_DIR"/{postgres,postgres-run,media,caddy,caddy-config,run,logs}
  chmod 700 "$DATA_DIR/postgres" 2>/dev/null || true
}

export_sources() {
  # A clean copy of the sources for the image builds (no .venv, node_modules, data or tests).
  rm -rf "$HERE/build"
  mkdir -p "$HERE/build"
  (cd "$ROOT" && git archive HEAD backend frontend | tar -x -C "$HERE/build")
  rm -rf "$HERE/build/backend/tests"
}

cmd_build() {
  need_apptainer
  mkdir -p "$IMAGES_DIR"
  export_sources
  local fakeroot=()
  if [ "${FAKEROOT:-auto}" != "no" ] && [ "$(id -u)" != "0" ]; then fakeroot=(--fakeroot); fi
  log "building postgres.sif"
  run "$APPTAINER" build --force "$IMAGES_DIR/postgres.sif" "$HERE/postgres.def"
  log "building redis.sif"
  run "$APPTAINER" build --force "$IMAGES_DIR/redis.sif" "$HERE/redis.def"
  log "building backend.sif (installs ffmpeg and Python packages)"
  (cd "$HERE" && run "$APPTAINER" build --force "${fakeroot[@]}" "$IMAGES_DIR/backend.sif" "$HERE/backend.def")
  log "building caddy.sif (builds the frontend)"
  (cd "$HERE" && run "$APPTAINER" build --force "${fakeroot[@]}" "$IMAGES_DIR/caddy.sif" "$HERE/caddy.def")
  rm -rf "$HERE/build"
  log "images in $IMAGES_DIR"
}

wait_for() {
  # wait_for <label> <seconds> <command...>
  local label="$1" seconds="$2"; shift 2
  [ "${DRY_RUN:-0}" = "1" ] && return 0
  local i=0
  until "$@" >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -ge "$seconds" ] && die "$label did not become ready in ${seconds}s (see: rugby.sh logs ${label})"
    sleep 1
  done
}

start_postgres() {
  instance_running postgres && { log "postgres already running"; return; }
  need_image postgres
  run "$APPTAINER" instance start --cleanenv --env-file "$(postgres_env_file)" \
    --bind "$DATA_DIR/postgres:/var/lib/postgresql/data" \
    --bind "$DATA_DIR/postgres-run:/var/run/postgresql" \
    "$IMAGES_DIR/postgres.sif" "$PREFIX-postgres" \
    -c listen_addresses=127.0.0.1 -c port="$POSTGRES_PORT"
  wait_for postgres 60 "$APPTAINER" exec "instance://$PREFIX-postgres" pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER"
}

start_redis() {
  instance_running redis && { log "redis already running"; return; }
  need_image redis
  run "$APPTAINER" instance start --cleanenv "$IMAGES_DIR/redis.sif" "$PREFIX-redis" \
    --bind 127.0.0.1 --port "$REDIS_PORT"
  wait_for redis 30 "$APPTAINER" exec "instance://$PREFIX-redis" redis-cli -p "$REDIS_PORT" ping
}

start_backend() {
  # start_backend <service> <role> [--nv]
  local service="$1" role="$2"; shift 2
  instance_running "$service" && { log "$service already running"; return; }
  need_image backend
  run "$APPTAINER" instance start "$@" --cleanenv --env-file "$(backend_env_file)" \
    --bind "$DATA_DIR/media:/data" \
    "$IMAGES_DIR/backend.sif" "$PREFIX-$service" "$role"
}

start_caddy() {
  instance_running caddy && { log "caddy already running"; return; }
  need_image caddy
  local binds=(--bind "$DATA_DIR/media:/srv/media:ro" --bind "$DATA_DIR/caddy:/data" --bind "$DATA_DIR/caddy-config:/config")
  if [ -f "$TLS_FILE" ]; then binds+=(--bind "$TLS_FILE:/etc/caddy/tls.caddy:ro"); fi
  if [ -n "$CERTS_DIR" ]; then binds+=(--bind "$CERTS_DIR:/certs:ro"); fi
  run "$APPTAINER" instance start --cleanenv --env-file "$(caddy_env_file)" "${binds[@]}" \
    "$IMAGES_DIR/caddy.sif" "$PREFIX-caddy"
}

cmd_start() {
  need_apptainer
  prepare_dirs
  local nv; nv="$(gpu_flag)"
  start_postgres
  start_redis
  start_backend api api
  wait_for api 120 "$APPTAINER" exec "instance://$PREFIX-api" python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$API_PORT/api/health', timeout=2)"
  # The transcode worker gets the GPU too so FFmpeg can use NVENC.
  start_backend worker-cpu worker-cpu ${nv:+$nv}
  start_backend worker-gpu worker-gpu ${nv:+$nv}
  start_caddy
  log "started. Open https://$SITE_ADDRESS:$HTTPS_PORT (GPU: ${nv:-not used})"
}

cmd_stop() {
  need_apptainer
  local s
  for s in caddy worker-gpu worker-cpu api redis postgres; do
    if instance_running "$s" || [ "${DRY_RUN:-0}" = "1" ]; then
      run "$APPTAINER" instance stop "$PREFIX-$s" || true
    fi
  done
}

cmd_status() {
  need_apptainer
  "$APPTAINER" instance list | grep -E "INSTANCE|$PREFIX-" || echo "no $PREFIX instances running"
}

cmd_logs() {
  local service="${1:-api}"; shift || true
  local dir="$HOME/.apptainer/instances/logs/$(hostname)/$(id -un)"
  local out="$dir/$PREFIX-$service.out" err="$dir/$PREFIX-$service.err"
  [ -f "$out" ] || [ -f "$err" ] || die "no logs yet for $service (looked in $dir)"
  if [ "${1:-}" = "-f" ]; then tail -n 50 -f "$out" "$err"; else tail -n 200 "$out" "$err"; fi
}

cmd_exec_api() {
  instance_running api || die "the api instance is not running (rugby.sh start)"
  run "$APPTAINER" exec "instance://$PREFIX-api" "$@"
}

cmd_create_admin() { cmd_exec_api python -m app.scripts.create_admin --email "$ADMIN_EMAIL" --name "$ADMIN_NAME" "$@"; }
cmd_seed() { cmd_exec_api python -m app.scripts.seed "$@"; }

cmd_backup() {
  local dest="${1:?destination directory}"
  mkdir -p "$dest"
  local file="$dest/rugby-$(date +%Y%m%d-%H%M%S).dump"
  run "$APPTAINER" exec "instance://$PREFIX-postgres" pg_dump -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$file"
  log "wrote $file"
  ls -1t "$dest"/rugby-*.dump 2>/dev/null | tail -n +31 | xargs -r rm --
}

cmd_shell() {
  local service="${1:-api}"
  run "$APPTAINER" shell "instance://$PREFIX-$service"
}

cmd_install_service() {
  # Writes a user-level systemd unit pointing at this checkout, wherever it lives.
  local dir="$HOME/.config/systemd/user" unit
  mkdir -p "$dir"
  unit="$dir/rugby.service"
  cat > "$unit" <<UNIT
[Unit]
Description=Rugby video analysis (Apptainer instances)
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$HERE/rugby.sh start
ExecStop=$HERE/rugby.sh stop
TimeoutStartSec=600

[Install]
WantedBy=default.target
UNIT
  log "wrote $unit"
  if command -v systemctl >/dev/null 2>&1; then
    run systemctl --user daemon-reload
    run systemctl --user enable rugby
    log "enabled. To keep it running when you are logged out:  loginctl enable-linger $(id -un)"
  else
    log "systemctl not found; the unit file is written but not enabled"
  fi
}

case "${1:-}" in
  build) cmd_build ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop; cmd_start ;;
  status) cmd_status ;;
  logs) shift; cmd_logs "$@" ;;
  create-admin) shift; cmd_create_admin "$@" ;;
  seed) shift; cmd_seed "$@" ;;
  backup) shift; cmd_backup "$@" ;;
  shell) shift; cmd_shell "$@" ;;
  install-service) cmd_install_service ;;
  *) sed -n '2,14p' "$0"; exit 1 ;;
esac
