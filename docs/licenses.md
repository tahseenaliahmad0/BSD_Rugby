# Licences of direct dependencies

Policy (ADR 0002): application dependencies are Apache-2.0, MIT, BSD, ISC or similar. Review
this list when adding a package. Checked 2026-10-13.

## Backend (Python)

| Package | Licence |
| --- | --- |
| fastapi, starlette | MIT, BSD-3 |
| uvicorn (with uvloop, httptools, watchfiles, websockets) | BSD-3 (MIT/Apache-2.0, MIT, MIT, BSD-3) |
| sqlalchemy | MIT |
| alembic | MIT |
| pg8000 | BSD-3 (chosen over psycopg, which is LGPL-3.0) |
| pydantic, pydantic-settings | MIT |
| email-validator | Unlicense |
| argon2-cffi | MIT |
| celery, kombu, billiard, vine | BSD-3 |
| redis (client) | MIT |
| pytest, httpx, ruff, mypy, celery-types (dev only) | MIT, BSD-3, MIT, MIT, Apache-2.0 |

## Frontend (npm)

| Package | Licence |
| --- | --- |
| react, react-dom | MIT |
| react-router | MIT |
| @mantine/core, @mantine/hooks, @mantine/notifications | MIT |
| @tanstack/react-query | MIT |
| @tabler/icons-react | MIT |
| tus-js-client | MIT |
| vite, @vitejs/plugin-react, vitest | MIT |
| typescript | Apache-2.0 |
| eslint, typescript-eslint, eslint-plugin-react-hooks, eslint-plugin-react-refresh | MIT |
| @playwright/test (dev only) | Apache-2.0 |
| postcss, postcss-preset-mantine, postcss-simple-vars | MIT |

## Services and tools (run as separate processes or containers, not linked)

| Component | Licence | Note |
| --- | --- | --- |
| PostgreSQL | PostgreSQL licence (permissive) | |
| Redis 7.2 | BSD-3 | Later Redis versions changed licence; Valkey (BSD-3) is a drop-in alternative |
| Caddy | Apache-2.0 | |
| FFmpeg (Debian build) | LGPL-2.1+ with GPL components such as libx264 | Called as a subprocess only; never linked into the application |
| Python 3.12 | PSF | |
| Node 22 | MIT | |

## Not used, by design

Ultralytics YOLO (AGPL-3.0) and any AGPL package. Later milestones default to RF-DETR
(Apache-2.0 sizes only) and Qwen3-VL (Apache-2.0).
