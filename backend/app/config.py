"""Application settings, read from the environment (and a .env file in development)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+pg8000://rugby:rugby@localhost:5432/rugby"
    redis_url: str = "redis://localhost:6379/0"

    # Where originals, proxies, thumbnails and in-progress uploads live.
    storage_root: Path = Path("./data")

    # Sessions and CSRF.
    session_cookie_name: str = "rugby_session"
    csrf_cookie_name: str = "rugby_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    session_ttl_days: int = 30
    cookie_secure: bool = False

    # Uploads (tus).
    upload_expiry_hours: int = 72

    # Transcoding.
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    transcode_encoder: Literal["auto", "libx264", "h264_nvenc"] = "auto"
    transcode_max_height: int = 1080
    transcode_crf: int = 21
    transcode_preset: str = "veryfast"
    thumbnail_interval_s: int = 10
    thumbnail_width: int = 240

    # Celery. When eager, tasks run inline in the calling process (tests, seed, e2e).
    celery_task_always_eager: bool = False

    # Whether the API serves /media itself (development). Caddy serves it in production.
    api_serves_media: bool = True

    # Bootstrap admin used by the seed script and create_admin when flags are omitted.
    admin_email: str = "admin@example.com"
    admin_password: str = Field(default="change-me-now")
    admin_name: str = "Admin"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
