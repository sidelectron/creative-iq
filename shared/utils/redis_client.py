"""Redis cache helpers and event stream publishing."""

import json
from typing import Any

import redis.asyncio as redis

from shared.config.settings import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a singleton async Redis client."""
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def cache_get(key: str) -> str | None:
    """Return cached string value or None."""
    r = get_redis()
    return await r.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    """Set a string value with TTL."""
    r = get_redis()
    await r.setex(key, ttl_seconds, value)


async def cache_delete(key: str) -> None:
    """Delete a cache key."""
    r = get_redis()
    await r.delete(key)


async def publish_event(payload: dict[str, Any]) -> str:
    """Append JSON payload to the configured Redis stream (XADD)."""
    r = get_redis()
    stream = settings.redis_events_stream
    message_id = await r.xadd(stream, {"payload": json.dumps(payload)})
    return str(message_id)
