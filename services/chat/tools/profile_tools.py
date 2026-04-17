"""Profile-oriented chat tools."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from services.chat.schemas import GenerateCreativeBriefInput, QueryBrandProfileInput
from services.chat.tools.common import tool
from shared.models.db import Brand, BrandProfile
from shared.utils.db_sync import sync_session
from shared.utils.gemini import generate_json
from shared.utils.redis_sync import cache_get_sync


@tool
def query_brand_profile(payload: QueryBrandProfileInput) -> dict[str, Any]:
    """Return current brand profile (cache first, DB fallback)."""
    brand_id = payload.brand_id
    platform = payload.platform
    if platform:
        key = f"brand_profile:{brand_id}:{platform}"
        cached = cache_get_sync(key)
        if cached:
            import json

            return json.loads(cached)
    with sync_session() as session:
        stmt = select(BrandProfile).where(BrandProfile.brand_id == brand_id)
        if platform:
            stmt = stmt.where(BrandProfile.platform == platform)
        row = session.scalar(stmt.order_by(BrandProfile.computed_at.desc()))
        if row is None:
            return {"status": "not_found"}
        profile = dict(row.profile_data or {})
        if payload.metric:
            profile["requested_metric"] = payload.metric
        return profile


@tool
def generate_creative_brief(payload: GenerateCreativeBriefInput) -> dict[str, Any]:
    """Generate data-grounded text brief from brand profile."""
    profile = query_brand_profile(QueryBrandProfileInput(brand_id=payload.brand_id))
    if profile.get("status") == "not_found":
        return {
            "brief": "No profile data yet. Use industry presets and run initial tests.",
            "confidence": "low",
        }
    if payload.user_id is not None:
        from services.generation.chat_dispatch import enqueue_generation_job

        job_id = enqueue_generation_job(
            brand_id=payload.brand_id,
            user_id=payload.user_id,
            campaign_description=payload.campaign_description,
            platform=payload.platform,
            num_variants=payload.num_variants,
        )
        return {
            "brief": (
                "Queued a full Phase 7 generation job (brief, compliance, variants). "
                f"Job id: {job_id}. Use GET /api/v1/brands/{{brand_id}}/generate/{job_id} or chat metadata to track status."
            ),
            "highlights": [f"generation_job_id={job_id}"],
            "confidence": "pending",
            "generation_job_id": str(job_id),
        }
    with sync_session() as session:
        brand = session.get(Brand, payload.brand_id)
        brand_name = brand.name if brand else "this brand"
    prompt = (
        f"Create a concise creative brief for {brand_name}. Campaign: {payload.campaign_description}. "
        f"Use this profile JSON: {profile}. Return JSON {{brief: string, highlights: string[]}}."
    )
    data, _, _ = generate_json(
        model="gemini-2.5-pro",
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        cache_key_parts={"brief_brand": str(payload.brand_id), "campaign": payload.campaign_description},
    )
    return {
        "brief": str(data.get("brief") or ""),
        "highlights": list(data.get("highlights") or []),
        "confidence": "mixed",
    }
