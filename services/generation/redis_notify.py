"""Redis pub/sub status updates for generation jobs (WebSocket consumers)."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import structlog

from shared.utils.redis_client import get_redis

log = structlog.get_logger()


async def publish_generation_update(
    job_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    """Publish JSON payload to channel `generation:{job_id}`."""
    try:
        r = get_redis()
        await r.publish(f"generation:{job_id}", json.dumps(payload))
    except Exception as err:
        log.warning("generation_pubsub_failed", job_id=str(job_id), error=str(err))


def publish_generation_update_sync(job_id: uuid.UUID, payload: dict[str, Any]) -> None:
    """Sync wrapper for Celery worker."""
    try:
        asyncio.run(publish_generation_update(job_id, payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(publish_generation_update(job_id, payload))
        finally:
            loop.close()
