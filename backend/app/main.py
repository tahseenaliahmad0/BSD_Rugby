"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    auth,
    catalog,
    events,
    health,
    jobs,
    media,
    squads,
    tags,
    templates,
    uploads,
    users,
    videos,
)
from app.config import get_settings
from app.core.csrf import CSRFMiddleware
from app.services.storage import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    get_storage()  # create the storage directories early so errors show at startup
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Rugby video analysis API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CSRFMiddleware,
        cookie_name=settings.csrf_cookie_name,
        header_name=settings.csrf_header_name,
    )
    for router in (
        health.router,
        auth.router,
        users.router,
        squads.router,
        catalog.router,
        events.router,
        videos.router,
        jobs.router,
        uploads.router,
        templates.router,
        tags.router,
    ):
        app.include_router(router, prefix="/api")
    app.include_router(media.router)
    return app


app = create_app()
