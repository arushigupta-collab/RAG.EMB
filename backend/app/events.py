"""Redis pub/sub bridge for live ingestion stage updates.

Celery workers publish per-stage updates (scope §10) to a per-job channel; the
FastAPI SSE endpoint subscribes and relays them to the corpus view. Kept tiny and
dependency-light so both the sync worker and the async API can use it.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import redis
import redis.asyncio as aredis

from app.config import settings


def _channel(job_id: str) -> str:
    return f"ingest:{job_id}"


# --- Worker side (sync) ---
_sync_client: redis.Redis | None = None


def _sync() -> redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.from_url(settings.redis_url)
    return _sync_client


def publish_stage(job_id: str, update: dict) -> None:
    # Best-effort: live SSE trace is a nice-to-have. If Redis is absent (e.g. a
    # single-process local run), the corpus view still reflects progress by
    # polling /documents, so a publish failure must not break ingestion.
    try:
        _sync().publish(_channel(job_id), json.dumps(update))
    except Exception:  # noqa: BLE001
        pass


def publish_done(job_id: str) -> None:
    try:
        _sync().publish(_channel(job_id), json.dumps({"event": "job_done"}))
    except Exception:  # noqa: BLE001
        pass


# --- API side (async) ---
async def subscribe_stages(job_id: str) -> AsyncIterator[dict]:
    client = aredis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(_channel(job_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            payload = json.loads(message["data"])
            yield payload
            if payload.get("event") == "job_done":
                break
    finally:
        await pubsub.unsubscribe(_channel(job_id))
        await pubsub.aclose()
        await client.aclose()
