# API and worker image. The same image runs `api`, `worker-cpu` and `worker-gpu`.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# FFmpeg (Debian build: libx264, AAC and the NVENC encoder; NVENC works when the container
# gets an NVIDIA device with the `video` driver capability).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY . .
RUN chmod +x docker/*.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["docker/start-api.sh"]
