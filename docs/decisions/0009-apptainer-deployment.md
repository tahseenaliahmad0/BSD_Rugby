# 0009. Deployment with Apptainer instead of Docker Compose

Status: accepted. Date: 2026-10-13. Amends the deployment row of the spec and ADR 0001.

## Context

The spec assumed Docker Compose with the NVIDIA Container Toolkit. College IT allows only
Apptainer (formerly Singularity) on the server: no Docker daemon, no root, no Compose, no
private container network. Apptainer runs rootless, shares the host network, mounts the host
filesystem with `--bind` and exposes NVIDIA GPUs with `--nv`. Its "instances" feature turned
out to be unusable on the server: rootless instances are placed in a cgroup through the
systemd user bus, and the server has no user session bus ("failed to connect to dbus").

## Decision

- The application does not change. The same backend and Caddy images are described twice:
  `Dockerfile`s for laptops and CI, and `deploy/apptainer/*.def` files for the server. The
  def files mirror the Dockerfiles line for line; CI builds both.
- Postgres and Redis are the official images wrapped in short def files with a `%runscript`.
  Both images already support running as a non-root user.
- `deploy/apptainer/rugby.sh` replaces Compose: it builds the four SIF images, creates the
  data directories, writes per-service env files, starts the six services in order with
  readiness checks, stops them in reverse, shows logs and status, and runs the admin, seed
  and backup commands with `apptainer exec` against the same images and binds.
- Each service is a plain background `apptainer run` started with `setsid nohup`, with a pid
  file under `DATA_DIR/run` and a log under `DATA_DIR/logs`. No instances, so no cgroups, no
  dbus and no systemd requirement; the launcher is the supervisor.
- Services talk over `127.0.0.1` ports instead of Compose service names. The Caddyfile reads
  `API_UPSTREAM`, `HTTP_PORT`, `HTTPS_PORT` and `MEDIA_ROOT` from the environment, with
  Compose-compatible defaults, so one Caddyfile serves both runtimes.
- A rootless process cannot bind ports 80 and 443, so Caddy listens on 8080 and 8443 by
  default. IT can lower `net.ipv4.ip_unprivileged_port_start` to allow 443, or front the app
  with the college's own reverse proxy.
- All state lives under one `DATA_DIR` on the host (postgres, media, caddy certificates,
  logs); images are read-only. The GPU is given to both workers so FFmpeg can use NVENC.
- After a reboot, `rugby.sh install-service` writes a user systemd unit when the server has a
  systemd user session; otherwise a crontab `@reboot` line calls `rugby.sh start`.

## Consequences

Docker Compose stays for developers and CI; the production path is Apptainer. The two must
stay in step: any change to a Dockerfile is mirrored in its def file (CI builds both). There
is no automatic restart of a crashed service: `rugby.sh status` shows it and `rugby.sh start`
brings it back (a cron line every few minutes can do that unattended). The launcher's process
handling was exercised against a fake `apptainer` in the development sandbox; the images and
the first real start were verified on the college server.
