#!/usr/bin/env bash
# Run the rugby video analysis app with Apptainer (no Docker, no root).
#
#   deploy/apptainer/rugby.sh build [name...] build the four images, or just the named ones
#                                            (postgres redis backend caddy); needs network
#   deploy/apptainer/rugby.sh start          start postgres, redis, api, workers, caddy (background processes)
#   deploy/apptainer/rugby.sh stop | restart | status
#   deploy/apptainer/rugby.sh check          status, listening ports and HTTP probes (run this when the site does not open)
#   deploy/apptainer/rugby.sh logs <service> [-f]
#   deploy/apptainer/rugby.sh create-admin   first administrator (prompts for a password)
#   deploy/apptainer/rugby.sh seed           demo squad and match (development only)
#   deploy/apptainer/rugby.sh backup <dir>   pg_dump into <dir>
#   deploy/apptainer/rugby.sh shell [backend|postgres|caddy]   a shell inside an image (backend has the app env)
#   deploy/apptainer/rugby.sh install-service   user systemd unit so it restarts after a reboot
#
# Services run on the host network: Postgres, Redis and the API bind 127.0.0.1; Caddy is the only
# public port. Each service is a background `apptainer run` with a pid file in DATA_DIR/run and a
# log in DATA_DIR/logs. Apptainer "instances" are not used because rootless instances need a
# systemd user bus for cgroups, which locked-down servers do not provide.
# Settings come from deploy/apptainer/rugby.env (see rugby.env.example).
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

pid_file() { echo "$DATA_DIR/run/$1.pid"; }
log_file() { echo "$DATA_DIR/logs/$1.log"; }

service_pid() {
  local f; f="$(pid_file "$1")"
  [ -f "$f" ] && cat "$f" 2>/dev/null || true
}

service_running() {
  [ "${DRY_RUN:-0}" = "1" ] && return 1
  local pid; pid="$(service_pid "$1")"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# launch <service> <apptainer args...>: a background `apptainer run`, detached from this shell.
launch() {
  local service="$1"; shift
  local logf; logf="$(log_file "$service")"
  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf '+ (background, log %s)' "$logf"; printf ' %q' "$APPTAINER" run "$@"; printf '\n'
    return 0
  fi
  setsid nohup "$APPTAINER" run "$@" >> "$logf" 2>&1 < /dev/null &
  echo $! > "$(pid_file "$service")"
  sleep 1
  if ! kill -0 "$(service_pid "$service")" 2>/dev/null; then
    die "$service exited at once; last lines of $logf:
$(tail -n 20 "$logf")"
  fi
}

stop_service() {
  local service="$1" pid
  pid="$(service_pid "$service")"
  if [ "${DRY_RUN:-0}" = "1" ]; then echo "+ kill -TERM <pid of $service>"; return 0; fi
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then rm -f "$(pid_file "$service")"; return 0; fi
  kill -TERM "$pid" 2>/dev/null || true
  local i=0
  while kill -0 "$pid" 2>/dev/null && [ $i -lt 30 ]; do sleep 1; i=$((i + 1)); done
  if kill -0 "$pid" 2>/dev/null; then log "$service did not stop in 30s; killing"; kill -KILL "$pid" 2>/dev/null || true; fi
  rm -f "$(pid_file "$service")"
  log "stopped $service"
}

# Apptainer reads --env-file with a shell parser (quotes and $VAR honoured,
# commands refused), so every value is single-quoted: `Head Analyst` or a
# password with $ or spaces would otherwise be parsed as a command.
env_line() {   # env_line NAME VALUE
  local v="${2//\'/\'\\\'\'}"
  printf "%s='%s'\n" "$1" "$v"
}

# Percent-encode a value for use inside a URL (the database password).
url_encode() {
  local LC_ALL=C s="$1" out="" c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [A-Za-z0-9._~-]) out+="$c" ;;
      *) out+="$(printf '%%%02X' "'$c")" ;;
    esac
  done
  printf '%s' "$out"
}

backend_env_file() {
  local f="$DATA_DIR/run/backend.env"
  mkdir -p "$DATA_DIR/run"
  {
    env_line APP_ENV production
    env_line DATABASE_URL "postgresql+pg8000://$(url_encode "$POSTGRES_USER"):$(url_encode "$POSTGRES_PASSWORD")@127.0.0.1:$POSTGRES_PORT/$POSTGRES_DB"
    env_line REDIS_URL "redis://127.0.0.1:$REDIS_PORT/0"
    env_line STORAGE_ROOT /data
    env_line COOKIE_SECURE true
    env_line API_SERVES_MEDIA false
    env_line API_HOST 127.0.0.1
    env_line API_PORT "$API_PORT"
    env_line TRANSCODE_ENCODER "$TRANSCODE_ENCODER"
    env_line WORKER_CONCURRENCY "$WORKER_CONCURRENCY"
    env_line ADMIN_EMAIL "$ADMIN_EMAIL"
    env_line ADMIN_NAME "$ADMIN_NAME"
    env_line ADMIN_PASSWORD "$ADMIN_PASSWORD"
  } > "$f"
  chmod 600 "$f"
  echo "$f"
}

site_addresses() {
  # Caddy serves the configured name plus localhost and 127.0.0.1, so the app also answers
  # through an SSH tunnel (ssh -L 8443:127.0.0.1:8443) whatever SITE_ADDRESS is.
  local list="$SITE_ADDRESS" extra
  for extra in localhost 127.0.0.1; do
    case ", $list, " in *", $extra, "*) ;; *) list="$list, $extra" ;; esac
  done
  echo "$list"
}

caddy_env_file() {
  local f="$DATA_DIR/run/caddy.env"
  mkdir -p "$DATA_DIR/run"
  {
    env_line SITE_ADDRESSES "$(site_addresses)"
    env_line HTTP_PORT "$HTTP_PORT"
    env_line HTTPS_PORT "$HTTPS_PORT"
    env_line API_UPSTREAM "127.0.0.1:$API_PORT"
    env_line MEDIA_ROOT /srv/media
  } > "$f"
  echo "$f"
}

postgres_env_file() {
  local f="$DATA_DIR/run/postgres.env"
  mkdir -p "$DATA_DIR/run"
  {
    env_line POSTGRES_USER "$POSTGRES_USER"
    env_line POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
    env_line POSTGRES_DB "$POSTGRES_DB"
    env_line PGPORT "$POSTGRES_PORT"
  } > "$f"
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

build_one() {
  local name="$1"
  case "$name" in
    postgres|redis)
      log "building $name.sif"
      run "$APPTAINER" build --force "$IMAGES_DIR/$name.sif" "$HERE/$name.def"
      ;;
    backend|caddy)
      local fakeroot=()
      if [ "${FAKEROOT:-auto}" != "no" ] && [ "$(id -u)" != "0" ]; then fakeroot=(--fakeroot); fi
      if [ "$name" = backend ]; then log "building backend.sif (installs ffmpeg and Python packages)"; else log "building caddy.sif (builds the frontend)"; fi
      (cd "$HERE" && run "$APPTAINER" build --force "${fakeroot[@]}" "$IMAGES_DIR/$name.sif" "$HERE/$name.def")
      ;;
    *) die "unknown image '$name' (postgres, redis, backend, caddy)" ;;
  esac
}

cmd_build() {
  need_apptainer
  mkdir -p "$IMAGES_DIR"
  local names=("$@")
  [ ${#names[@]} -eq 0 ] && names=(postgres redis backend caddy)
  export_sources
  local name
  for name in "${names[@]}"; do build_one "$name"; done
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

backend_args() {
  echo --cleanenv --env-file "$(backend_env_file)" --bind "$DATA_DIR/media:/data" "$IMAGES_DIR/backend.sif"
}

start_postgres() {
  service_running postgres && { log "postgres already running"; return; }
  need_image postgres
  launch postgres --cleanenv --env-file "$(postgres_env_file)" \
    --bind "$DATA_DIR/postgres:/var/lib/postgresql/data" \
    --bind "$DATA_DIR/postgres-run:/var/run/postgresql" \
    "$IMAGES_DIR/postgres.sif" postgres -c listen_addresses=127.0.0.1 -c port="$POSTGRES_PORT"
  wait_for postgres 60 "$APPTAINER" exec "$IMAGES_DIR/postgres.sif" pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER"
}

start_redis() {
  service_running redis && { log "redis already running"; return; }
  need_image redis
  launch redis --cleanenv "$IMAGES_DIR/redis.sif" --save "" --appendonly no --bind 127.0.0.1 --port "$REDIS_PORT"
  wait_for redis 30 "$APPTAINER" exec "$IMAGES_DIR/redis.sif" redis-cli -p "$REDIS_PORT" ping
}

start_backend() {
  # start_backend <service> <role> [--nv]
  local service="$1" role="$2"; shift 2
  service_running "$service" && { log "$service already running"; return; }
  need_image backend
  # shellcheck disable=SC2046
  launch "$service" "$@" $(backend_args) "$role"
}

start_caddy() {
  service_running caddy && { log "caddy already running"; return; }
  need_image caddy
  # The checkout's Caddyfile is bound over the one baked into the image, so a `git pull` and a
  # restart pick up config changes without rebuilding the image.
  local binds=(--bind "$ROOT/deploy/Caddyfile:/etc/caddy/Caddyfile:ro"
               --bind "$DATA_DIR/media:/srv/media:ro" --bind "$DATA_DIR/caddy:/data" --bind "$DATA_DIR/caddy-config:/config")
  if [ -f "$TLS_FILE" ]; then binds+=(--bind "$TLS_FILE:/etc/caddy/tls.caddy:ro"); fi
  if [ -n "$CERTS_DIR" ]; then binds+=(--bind "$CERTS_DIR:/certs:ro"); fi
  launch caddy --cleanenv --env-file "$(caddy_env_file)" "${binds[@]}" "$IMAGES_DIR/caddy.sif" \
    run --config /etc/caddy/Caddyfile --adapter caddyfile
}

cmd_start() {
  need_apptainer
  prepare_dirs
  local nv; nv="$(gpu_flag)"
  start_postgres
  start_redis
  start_backend api api
  wait_for api 180 "$APPTAINER" exec "$IMAGES_DIR/backend.sif" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$API_PORT/api/health', timeout=2)"
  # The transcode worker gets the GPU too so FFmpeg can use NVENC.
  start_backend worker-cpu worker-cpu ${nv:+$nv}
  start_backend worker-gpu worker-gpu ${nv:+$nv}
  start_caddy
  log "started. Open https://$SITE_ADDRESS:$HTTPS_PORT, or https://localhost:$HTTPS_PORT through an SSH tunnel (GPU: ${nv:-not used}). Logs: $DATA_DIR/logs"
}

probe() {   # probe <label> <url> [curl args...]: prints the response body and HTTP status
  local label="$1" url="$2" out; shift 2
  if command -v curl >/dev/null 2>&1; then
    # --noproxy: everything probed here is on this machine, whatever http_proxy says.
    out="$(curl -sSk -m 5 --noproxy '*' -w ' (HTTP %{http_code})' "$@" "$url" 2>&1)" || true
  else
    out="$("$APPTAINER" exec "$IMAGES_DIR/backend.sif" python -c "
import ssl, urllib.request, urllib.error
try:
    r = urllib.request.urlopen('$url', timeout=5, context=ssl._create_unverified_context())
    print(r.read().decode(errors='replace'), '(HTTP %d)' % r.status)
except urllib.error.HTTPError as e:
    print('(HTTP %d)' % e.code)
except Exception as e:
    print('error:', e)
" 2>&1)" || true
  fi
  out="${out//$'\n'/ }"
  printf '  %-16s %-48s %s\n' "$label" "$url" "$out"
}

cmd_check() {
  cmd_status
  echo
  echo "Listening TCP ports (expected: $HTTPS_PORT and $HTTP_PORT for caddy, $API_PORT api, $POSTGRES_PORT postgres, $REDIS_PORT redis):"
  local ports="($HTTPS_PORT|$HTTP_PORT|$API_PORT|$POSTGRES_PORT|$REDIS_PORT)"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk 'NR > 1 {print "  " $4}' | grep -E ":$ports\$" || echo "  (none of the expected ports is listening)"
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | awk '/LISTEN/ {print "  " $4}' | grep -E ":$ports\$" || echo "  (none of the expected ports is listening)"
  else
    echo "  (neither ss nor netstat is installed; the probes below still tell)"
  fi
  echo
  echo "Probes (expect {\"status\":\"ok\",\"database\":\"ok\"} and HTTP 200 on every line):"
  probe "api direct" "http://127.0.0.1:$API_PORT/api/health"
  probe "caddy by ip" "https://127.0.0.1:$HTTPS_PORT/api/health"
  probe "caddy localhost" "https://localhost:$HTTPS_PORT/api/health"
  if [ "$SITE_ADDRESS" != "localhost" ] && command -v curl >/dev/null 2>&1; then
    probe "caddy site name" "https://$SITE_ADDRESS:$HTTPS_PORT/api/health" --resolve "$SITE_ADDRESS:$HTTPS_PORT:127.0.0.1"
  fi
  probe "http redirect" "http://127.0.0.1:$HTTP_PORT/" -o /dev/null
  echo
  echo "From a laptop:  ssh -L $HTTPS_PORT:127.0.0.1:$HTTPS_PORT <you>@<this server>   then open https://localhost:$HTTPS_PORT"
  echo "                (type the https:// part; accept the certificate warning once)"
  if [ -f "$(log_file caddy)" ]; then
    echo
    echo "Last 15 lines of the caddy log:"
    tail -n 15 "$(log_file caddy)" | sed 's/^/  /'
  fi
}

cmd_stop() {
  local s
  for s in caddy worker-gpu worker-cpu api redis postgres; do stop_service "$s"; done
}

cmd_status() {
  local s pid state
  printf '%-12s %-8s %s\n' SERVICE STATE PID
  for s in "${SERVICES[@]}"; do
    pid="$(service_pid "$s")"
    if service_running "$s"; then state=running; else state=stopped; pid=""; fi
    printf '%-12s %-8s %s\n' "$s" "$state" "$pid"
  done
}

cmd_logs() {
  local service="${1:-api}"; shift || true
  local logf; logf="$(log_file "$service")"
  [ -f "$logf" ] || die "no log yet for $service (looked for $logf)"
  if [ "${1:-}" = "-f" ]; then tail -n 50 -f "$logf"; else tail -n 200 "$logf"; fi
}

cmd_exec_backend() {
  need_image backend
  # --pwd /app: apptainer exec keeps the host's working directory, and `python -m app...`
  # needs to start from the application directory.
  # shellcheck disable=SC2046
  run "$APPTAINER" exec --pwd /app $(backend_args) "$@"
}

cmd_create_admin() {
  service_running postgres || [ "${DRY_RUN:-0}" = "1" ] || die "postgres is not running (rugby.sh start)"
  cmd_exec_backend python -m app.scripts.create_admin --email "$ADMIN_EMAIL" --name "$ADMIN_NAME" "$@"
}
cmd_seed() {
  service_running postgres || [ "${DRY_RUN:-0}" = "1" ] || die "postgres is not running (rugby.sh start)"
  cmd_exec_backend python -m app.scripts.seed "$@"
}

cmd_backup() {
  local dest="${1:?destination directory}"
  mkdir -p "$dest"
  local file="$dest/rugby-$(date +%Y%m%d-%H%M%S).dump"
  run "$APPTAINER" exec --cleanenv --env "PGPASSWORD=$POSTGRES_PASSWORD" "$IMAGES_DIR/postgres.sif" \
    pg_dump -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$file"
  log "wrote $file"
  ls -1t "$dest"/rugby-*.dump 2>/dev/null | tail -n +31 | xargs -r rm --
}

cmd_shell() {
  case "${1:-backend}" in
    postgres) run "$APPTAINER" shell --cleanenv --env "PGPASSWORD=$POSTGRES_PASSWORD" "$IMAGES_DIR/postgres.sif" ;;
    caddy) run "$APPTAINER" shell "$IMAGES_DIR/caddy.sif" ;;
    *) # shellcheck disable=SC2046
       run "$APPTAINER" shell --pwd /app $(backend_args) ;;
  esac
}

cmd_install_service() {
  # Writes a user-level systemd unit pointing at this checkout, wherever it lives.
  local dir="$HOME/.config/systemd/user" unit
  mkdir -p "$dir"
  unit="$dir/rugby.service"
  cat > "$unit" <<UNIT
[Unit]
Description=Rugby video analysis (Apptainer services)
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
  build) shift; cmd_build "$@" ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop; cmd_start ;;
  status) cmd_status ;;
  check) cmd_check ;;
  logs) shift; cmd_logs "$@" ;;
  create-admin) shift; cmd_create_admin "$@" ;;
  seed) shift; cmd_seed "$@" ;;
  backup) shift; cmd_backup "$@" ;;
  shell) shift; cmd_shell "$@" ;;
  install-service) cmd_install_service ;;
  *) sed -n '2,14p' "$0"; exit 1 ;;
esac
