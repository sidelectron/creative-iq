"""Memory timeline/event tools."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from services.chat import events_service, memory_search, timeline_service
from services.chat.schemas import AddBrandEventInput, SearchBrandMemoryInput, UpdateUserPreferenceInput
from services.chat.tools.common import tool
from shared.models.db import UserBrandPreference
from shared.utils.db_sync import sync_session


@tool
def search_brand_memory(payload: SearchBrandMemoryInput) -> list[dict[str, Any]]:
    """Semantic search over brand events with optional date filters."""
    with sync_session() as session:
        return memory_search.search_events(
            session,
            brand_id=payload.brand_id,
            query=payload.query,
            top_k=payload.limit,
            start_date=payload.date_range_start,
            end_date=payload.date_range_end,
        )


@tool
def get_brand_timeline(
    brand_id: uuid.UUID,
    limit: int = 20,
    event_type_filter: str | None = None,
    date_range_start: datetime | None = None,
    date_range_end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return merged timeline items for a brand."""
    with sync_session() as session:
        items, _ = timeline_service.list_timeline_items(
            session,
            brand_id=brand_id,
            event_type=event_type_filter,
            source=None,
            start_date=date_range_start,
            end_date=date_range_end,
            page=1,
            page_size=limit,
        )
        return items


@tool
def add_brand_event(payload: AddBrandEventInput) -> dict[str, Any]:
    """Create a user-provided brand event and return summary."""
    with sync_session() as session:
        row = events_service.create_event(
            session,
            brand_id=payload.brand_id,
            event_type=payload.event_type,
            title=payload.title,
            event_date=payload.event_date,
            description=payload.description,
            impact_tags=payload.impact_tags,
            is_era_creating=payload.is_era_creating,
        )
        return {
            "event_id": str(row.id),
            "event_type": row.event_type,
            "title": row.title,
            "event_date": row.event_date.isoformat(),
            "is_era_creating": bool((row.event_metadata or {}).get("is_era_creating")),
        }


@tool
def update_user_preferences(payload: UpdateUserPreferenceInput) -> dict[str, Any]:
    """Update per-user brand preferences used by chat recommendations."""
    with sync_session() as session:
        pref = session.scalar(
            select(UserBrandPreference).where(
                UserBrandPreference.user_id == payload.user_id,
                UserBrandPreference.brand_id == payload.brand_id,
            )
        )
        if pref is None:
            pref = UserBrandPreference(
                user_id=payload.user_id,
                brand_id=payload.brand_id,
            )
            session.add(pref)
        if payload.field == "success_metrics":
            pref.success_metrics = payload.value
        elif payload.field == "creative_preferences":
            pref.creative_preferences = payload.value
        elif payload.field == "strategic_notes":
            pref.strategic_notes = str(payload.value)
        else:
            raise ValueError("Unsupported preference field")
        session.add(pref)
        session.commit()
        return {
            "status": "updated",
            "field": payload.field,
            "brand_id": str(payload.brand_id),
            "user_id": str(payload.user_id),
        }
