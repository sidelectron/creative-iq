"""Synchronous Redis helpers for Celery worker."""

from __future__ import annotations

import json
from typing import Any

import redis

from shared.config.settings import settings

_client: redis.Redis | None = None


def get_redis_sync() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def cache_get_sync(key: str) -> str | None:
    return get_redis_sync().get(key)


def cache_setex_sync(key: str, ttl_seconds: int, value: str) -> None:
    get_redis_sync().setex(key, ttl_seconds, value)


def publish_event_sync(payload: dict[str, Any]) -> str:
    r = get_redis_sync()
    message_id = r.xadd(settings.redis_events_stream, {"payload": json.dumps(payload)})
    return str(message_id)


def celery_queue_length(queue_name: str) -> int:
    """Approximate Celery Redis broker queue depth (list length)."""
    r = get_redis_sync()
    key = queue_name
    if r.exists(key):
        return int(r.llen(key))
    return 0
