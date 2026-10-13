# Running on the college server with Apptainer

The server has Apptainer, no Docker. Everything runs as your own user: four images, six
background processes, one data directory. Decisions in `docs/decisions/0009-apptainer-deployment.md`.

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

Then open `https://<SITE_ADDRESS>:8443`. Caddy also answers for the server's own host name
and IP address (`hostname -f`, `hostname -I`), so `https://<server-ip>:8443` works from the
college network without any configuration. The browser warns about the certificate until you
either install the college certificate (copy `tls.caddy.example` to `tls.caddy`, set
`CERTS_DIR` in `rugby.env`, restart) or trust Caddy's local authority.

`rugby.sh check` is the first thing to run when the site does not open: it prints the
service table, which ports are listening, and probes the API directly, through Caddy by IP,
by `localhost` and by the site name, each with the HTTP status.

## From a laptop through SSH

When the server's port is not reachable from your network, tunnel it:

```bash
ssh -L 8443:127.0.0.1:8443 you@server      # keep this session open
```

and open `https://localhost:8443` (type the `https://`; a bare `localhost:8443` is sent as
plain HTTP and Caddy answers "Client sent an HTTP request to an HTTPS server"). Caddy
serves `localhost` and `127.0.0.1` alongside `SITE_ADDRESS` for this reason. With Caddy's
own certificate the browser warns once; with a college certificate issued for the real name
the tunnel still works but the warning is about the name, so either accept it or add
`127.0.0.1 <SITE_ADDRESS>` to your laptop's hosts file and use the real name.

`rugby.sh status` lists the six services, `rugby.sh logs api` (or `postgres`, `redis`,
`worker-cpu`, `worker-gpu`, `caddy`; add `-f` to follow) shows their output, `rugby.sh stop`
stops them all. Logs live in `DATA_DIR/logs`, pid files in `DATA_DIR/run`.

## Upgrades

```bash
cd ~/Desktop/bsd && git pull
deploy/apptainer/rugby.sh build && deploy/apptainer/rugby.sh restart
```

Database migrations run when the api service starts. A change that only touches
`deploy/Caddyfile` or `rugby.sh` needs no build: the launcher binds the checkout's Caddyfile
into the Caddy container, so `git pull` and `rugby.sh restart` are enough.

## After a reboot

If the server gives you a systemd user session (`systemctl --user status` works), install the
user service once; it is written with the path of your checkout:

```bash
deploy/apptainer/rugby.sh install-service
loginctl enable-linger "$USER"     # keep it running when nobody is logged in
```

If it does not (the usual sign is "Failed to connect to bus"), use cron instead. `crontab -e`
and add one line, which also restarts anything that has crashed:

```
*/5 * * * * $HOME/Desktop/bsd/deploy/apptainer/rugby.sh start >> $HOME/rugby-data/logs/cron.log 2>&1
```

`start` is safe to repeat: services that are already running are left alone.

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

Check these the first time:

1. `rugby.sh build` finishes and `deploy/apptainer/images/` holds four `.sif` files.
2. `rugby.sh start` prints `started`; `rugby.sh status` shows six services `running`.
3. `rugby.sh logs postgres` shows `database system is ready to accept connections`; if it
   complains about permissions on `/var/lib/postgresql/data`, make sure `DATA_DIR/postgres`
   is empty and owned by you.
4. `curl -k https://localhost:8443/api/health` returns `{"status":"ok","database":"ok"}`.
5. Sign in, upload a short clip, and check `rugby.sh logs worker-cpu` for the transcode and
   whether it chose `h264_nvenc` or `libx264`.

Errors seen on the college server and what they mean:

- `failed to connect to dbus` from `apptainer instance start`: rootless instances need a
  systemd user session. The launcher no longer uses instances.
- `exec /.singularity.d/libs/fakeroot failed` while building: a `%post` section in an Alpine
  stage. All stages with `%post` use Debian bases.
- `caddy: Value too large for data type` in `logs caddy`: the binary carries a file
  capability (the official image sets `cap_net_bind_service`), which a rootless run cannot
  execute. `rugby.sh build caddy` rebuilds the image without it.
- `/api/health` answers but the site itself is a 404 page: the frontend was copied to
  `/srv/dist` instead of `/srv` by an older `caddy.def`; `rugby.sh build caddy` fixes it.
- `failed to install root certificate ... tee: exit status 1` in `logs caddy`: harmless,
  Caddy tried to add its local CA to the system trust store; newer Caddyfiles skip that.
- `No module named 'app'` from `create-admin` or `seed`: an old launcher ran the command from
  the host's working directory; `git pull` fixes it.
