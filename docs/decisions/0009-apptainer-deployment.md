# 0009. Deployment with Apptainer instead of Docker Compose

Status: accepted. Date: 2026-10-13. Amends the deployment row of the spec and ADR 0001.

## Context

The spec assumed Docker Compose with the NVIDIA Container Toolkit. College IT allows only
Apptainer (formerly Singularity) on the server: no Docker daemon, no root, no Compose, no
private container network. Apptainer runs rootless, shares the host network, mounts the host
filesystem with `--bind`, exposes NVIDIA GPUs with `--nv`, and runs background services as
"instances" with a `%startscript`.

## Decision

- The application does not change. The same backend and Caddy images are described twice:
  `Dockerfile`s for laptops and CI, and `deploy/apptainer/*.def` files for the server. The
  def files mirror the Dockerfiles line for line; CI builds both.
- Postgres and Redis are the official images wrapped in two-line def files that add a
  `%startscript`, so they run as instances like everything else. Both images already support
  running as a non-root user.
- `deploy/apptainer/rugby.sh` replaces Compose: it builds the four SIF images, creates the
  data directories, writes per-service env files, starts the six instances in order with
  readiness checks, stops them in reverse, shows logs and status, and runs the admin, seed
  and backup commands inside the running instances.
- Services talk over `127.0.0.1` ports instead of Compose service names. The Caddyfile reads
  `API_UPSTREAM`, `HTTP_PORT`, `HTTPS_PORT` and `MEDIA_ROOT` from the environment, with
  Compose-compatible defaults, so one Caddyfile serves both runtimes.
- A rootless process cannot bind ports 80 and 443, so Caddy listens on 8080 and 8443 by
  default. IT can lower `net.ipv4.ip_unprivileged_port_start` to allow 443, or front the app
  with the college's own reverse proxy.
- All state lives under one `DATA_DIR` on the host (postgres, media, caddy certificates,
  logs); images are read-only. The GPU is given to both workers so FFmpeg can use NVENC.
- A user systemd unit (`rugby.service`) with lingering enabled brings the instances back after
  a reboot without root.

## Consequences

Docker Compose stays for developers and CI; the production path is Apptainer. The two must
stay in step: any change to a Dockerfile is mirrored in its def file (CI builds both).
Apptainer's own limits apply: no health-check restarts (the launcher checks readiness at
start only; the systemd unit restarts everything on reboot), and logs go to
`~/.apptainer/instances/logs`. The Apptainer path could not be run inside the development
sandbox used to build this; the launcher was exercised in dry-run mode and the def files
mirror Dockerfiles that CI builds. The first start on the server must follow the checklist in
`deploy/apptainer/README.md`.
