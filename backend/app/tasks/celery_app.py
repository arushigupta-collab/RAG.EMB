"""Celery application for asynchronous bulk ingestion (scope §5.1, step 1)."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "mnre",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ingest_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,  # one heavy doc per worker slot at a time
    # Single-process local run: tasks execute inline, no broker/worker needed.
    task_always_eager=settings.celery_eager,
    task_eager_propagates=False,
)
