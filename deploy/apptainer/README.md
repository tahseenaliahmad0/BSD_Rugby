# Running on the college server with Apptainer

The server has Apptainer, no Docker. Everything runs as your own user: four images, six
background instances, one data directory. Decisions in `docs/decisions/0009-apptainer-deployment.md`.

## What you need on the server

- Apptainer 1.1 or newer (`apptainer --version`). Building the backend and Caddy images
  installs packages under `--fakeroot`. On most installs this works out of the box through a
  root-mapped user namespace (the build prints "trying root-mapped namespace"); if it refuses,
  ask IT for `apptainer config fakeroot --add $USER`, or build on another machine and copy the
  `.sif` files into `deploy/apptainer/images/`.
- Outbound network during `build` (Docker Hub, Debian, PyPI, npm).
- For the GPU: the NVIDIA driver on the host and `nvidia-smi` on your PATH (Apptainer's
  `--nv` does the rest). Without a GPU everything runs on the CPU.
- About 6 GB free for images and build caches, plus the footage.

## First install

You are not root, so everything goes under your home directory (or any folder you own). The
examples use `~/Desktop/bsd`; any path works, the launcher finds its own location:

```bash
cd ~/Desktop
git clone <this repository> bsd
cd ~/Desktop/bsd
cp deploy/apptainer/rugby.env.example deploy/apptainer/rugby.env
nano deploy/apptainer/rugby.env                 # DATA_DIR, SITE_ADDRESS, passwords, admin
deploy/apptainer/rugby.sh build                 # 10 to 20 minutes the first time
# (rugby.sh build caddy   rebuilds one image; names: postgres redis backend caddy)
deploy/apptainer/rugby.sh start
deploy/apptainer/rugby.sh create-admin          # prompts for the admin password
```

Then open `https://<SITE_ADDRESS>:8443`. The browser warns about the certificate until you
either install the college certificate (copy `tls.caddy.example` to `tls.caddy`, set
`CERTS_DIR` in `rugby.env`, restart) or trust Caddy's local authority.

`rugby.sh status` lists the instances, `rugby.sh logs api` (or `postgres`, `redis`,
`worker-cpu`, `worker-gpu`, `caddy`) shows their output, `rugby.sh stop` stops them all.

## Upgrades

```bash
cd ~/Desktop/bsd && git pull
deploy/apptainer/rugby.sh build && deploy/apptainer/rugby.sh restart
```

Database migrations run when the api instance starts.

## After a reboot

Install the user service once; it is written with the path of your checkout:

```bash
deploy/apptainer/rugby.sh install-service
loginctl enable-linger "$USER"     # keep it running when nobody is logged in
```

## Backups

`deploy/apptainer/rugby.sh backup ~/rugby-backups` writes a `pg_dump` and keeps the last
30. Add it to your crontab nightly. Back up `DATA_DIR/media/originals` under IT's storage
policy; proxies, thumbnails and exports can be regenerated.

## Ports

| Service | Listens on | Change with |
| --- | --- | --- |
| Caddy (the app) | `0.0.0.0:8443` HTTPS, `:8080` redirects | `HTTPS_PORT`, `HTTP_PORT` |
| API | `127.0.0.1:8000` | `API_PORT` |
| Postgres | `127.0.0.1:5432` | `POSTGRES_PORT` |
| Redis | `127.0.0.1:6379` | `REDIS_PORT` |

If the server already runs Postgres or Redis on those ports, change the ports; nothing else
needs to know.

## First-start checklist (what to verify on the server)

This deployment path could not be executed in the environment the app was built in, so
check these the first time:

1. `rugby.sh build` finishes and `deploy/apptainer/images/` holds four `.sif` files.
2. `rugby.sh start` prints `started`; `rugby.sh status` shows six `rugby-*` instances.
3. `rugby.sh logs postgres` shows `database system is ready to accept connections`; if it
   complains about permissions on `/var/lib/postgresql/data`, make sure `DATA_DIR/postgres`
   is empty and owned by you.
4. `curl -k https://localhost:8443/api/health` returns `{"status":"ok","database":"ok"}`.
5. Sign in, upload a short clip, and check `rugby.sh logs worker-cpu` for the transcode and
   whether it chose `h264_nvenc` or `libx264`.
