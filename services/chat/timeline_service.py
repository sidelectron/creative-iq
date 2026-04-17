"""Unified timeline service."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.db import ABTest, BrandEra, BrandEvent, BrandProfile


def list_timeline_items(
    session: Session,
    *,
    brand_id: uuid.UUID,
    event_type: str | None,
    source: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    items: list[dict] = []
    for row in session.scalars(select(BrandEvent).where(BrandEvent.brand_id == brand_id)).all():
        items.append(
            {
                "timestamp": row.event_date,
                "event_type": row.event_type,
                "title": row.title,
                "description": row.description,
                "source": row.source,
                "impact": dict(row.event_metadata or {}),
                "related_data": {"event_id": str(row.id)},
            }
        )
    for row in session.scalars(select(BrandEra).where(BrandEra.brand_id == brand_id)).all():
        items.append(
            {
                "timestamp": row.start_date,
                "event_type": "era_boundary",
                "title": row.era_name,
                "description": row.context_summary,
                "source": "system",
                "impact": {},
                "related_data": {"era_id": str(row.id), "triggering_event_id": str(row.triggering_event_id or "")},
            }
        )
    for row in session.scalars(select(ABTest).where(ABTest.brand_id == brand_id)).all():
        items.append(
            {
                "timestamp": row.created_at,
                "event_type": f"ab_test_{row.status}",
                "title": f"A/B test {row.status}: {row.attribute_tested}",
                "description": row.hypothesis,
                "source": "user_provided" if row.status == "proposed" else "auto_detected",
                "impact": dict(row.results or {}),
                "related_data": {"test_id": str(row.id), "status": row.status},
            }
        )
    for row in session.scalars(select(BrandProfile).where(BrandProfile.brand_id == brand_id)).all():
        items.append(
            {
                "timestamp": row.computed_at,
                "event_type": "profile_computed",
                "title": f"Profile computed for {row.platform}",
                "description": f"Scoring stage: {row.scoring_stage}",
                "source": "system",
                "impact": {"overall_confidence": float(row.overall_confidence or 0.0)},
                "related_data": {"platform": row.platform},
            }
        )
    if event_type:
        items = [item for item in items if item["event_type"] == event_type]
    if source:
        items = [item for item in items if item["source"] == source]
    if start_date:
        items = [item for item in items if item["timestamp"] >= start_date]
    if end_date:
        items = [item for item in items if item["timestamp"] <= end_date]
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    total = len(items)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size], total
