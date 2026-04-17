"""Context loader node for chat graph."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.chat.state import ChatTurnState
from shared.models.db import Brand, BrandEra, BrandEvent, BrandProfile, Message, UserBrandPreference
from shared.utils.redis_client import cache_get


async def load_context(
    *,
    db: AsyncSession,
    state: ChatTurnState,
) -> ChatTurnState:
    brand_id = state["brand_id"]
    profile_payload: dict[str, Any] | None = None
    platform_hint = str((state.get("working_memory") or {}).get("platform") or "")
    if platform_hint:
        cached = await cache_get(f"brand_profile:{brand_id}:{platform_hint}")
        if cached:
            profile_payload = json.loads(cached)
    if profile_payload is None:
        row = await db.scalar(
            select(BrandProfile)
            .where(BrandProfile.brand_id == brand_id, BrandProfile.audience_segment == "all")
            .order_by(BrandProfile.computed_at.desc())
        )
        profile_payload = dict(row.profile_data or {}) if row is not None else None
    brand = await db.scalar(select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None)))
    active_era = await db.scalar(
        select(BrandEra)
        .where(BrandEra.brand_id == brand_id, BrandEra.end_date.is_(None))
        .order_by(BrandEra.start_date.desc())
    )
    recent_events = list(
        (
            await db.scalars(
                select(BrandEvent)
                .where(BrandEvent.brand_id == brand_id)
                .order_by(BrandEvent.event_date.desc())
                .limit(5)
            )
        ).all()
    )
    pref = await db.scalar(
        select(UserBrandPreference).where(
            UserBrandPreference.brand_id == brand_id,
            UserBrandPreference.user_id == state["user_id"],
        )
    )
    history: list[dict[str, Any]] = []
    if state.get("conversation_id"):
        rows = list(
            (
                await db.scalars(
                    select(Message)
                    .where(Message.conversation_id == state["conversation_id"])
                    .order_by(Message.created_at.desc())
                    .limit(20)
                )
            ).all()
        )
        history = [
            {
                "role": msg.role,
                "content": msg.content,
                "agent_type": msg.agent_type,
                "tool_calls": msg.tool_calls,
                "sources": msg.sources,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in reversed(rows)
        ]
    state["brand_profile"] = profile_payload
    state["brand_info"] = (
        {
            "name": brand.name,
            "industry": brand.industry,
            "success_metrics": list(brand.success_metrics or []),
            "website_url": brand.website_url,
        }
        if brand
        else {}
    )
    state["recent_events"] = [
        {
            "event_id": str(evt.id),
            "event_type": evt.event_type,
            "title": evt.title,
            "event_date": evt.event_date.isoformat(),
            "source": evt.source,
        }
        for evt in recent_events
    ]
    state["current_era"] = (
        {
            "era_name": active_era.era_name,
            "start_date": active_era.start_date.isoformat(),
            "triggering_event_id": str(active_era.triggering_event_id or ""),
        }
        if active_era
        else None
    )
    state["user_preferences"] = (
        {
            "success_metrics": pref.success_metrics,
            "creative_preferences": pref.creative_preferences,
            "strategic_notes": pref.strategic_notes,
        }
        if pref
        else None
    )
    state["conversation_history"] = history
    return state
