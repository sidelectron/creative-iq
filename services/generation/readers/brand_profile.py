"""Async brand profile load for generation (Redis cache, then Postgres)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.db import BrandProfile
from shared.utils.redis_client import cache_get


async def load_brand_profile_payload(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    platform: str,
) -> dict[str, Any] | None:
    """Return profile_data dict or None — same cache key pattern as chat tools."""
    key = f"brand_profile:{brand_id}:{platform}"
    cached = await cache_get(key)
    if cached:
        return json.loads(cached)
    row = await db.scalar(
        select(BrandProfile)
        .where(
            BrandProfile.brand_id == brand_id,
            BrandProfile.platform == platform,
            BrandProfile.audience_segment == "all",
        )
        .order_by(BrandProfile.computed_at.desc())
    )
    if row is None:
        return None
    return dict(row.profile_data or {})
