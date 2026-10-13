"""Celery application with separate `cpu` and `gpu` queues.

Run a CPU worker with:  celery -A app.workers.celery_app worker -Q cpu
Run a GPU worker with:  celery -A app.workers.celery_app worker -Q gpu --concurrency=1
"""

from __future__ import annotations

from celery import Celery
from kombu import Queue

from app.config import get_settings

settings = get_settings()

celery_app = Celery("rugby", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_default_queue="cpu",
    task_queues=(Queue("cpu"), Queue("gpu")),
    task_routes={
        "app.workers.tasks.transcode_video": {"queue": "cpu"},
        "app.workers.tasks.gpu_ping": {"queue": "gpu"},
    },
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
)
celery_app.autodiscover_tasks(["app.workers"], related_name="tasks")
