"""A/B test related tools."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from services.ab_testing.designer import design_test
from services.chat.schemas import DesignAbTestInput
from services.chat.tools.common import tool
from shared.models.db import BrandProfile
from shared.utils.db_sync import sync_session


@tool
def design_ab_test(payload: DesignAbTestInput) -> dict[str, Any]:
    """Design an A/B test plan for an attribute and variants."""
    plan = design_test(
        brand_id=payload.brand_id,
        created_by=uuid.uuid4(),
        attribute_to_test=payload.attribute,
        variants=payload.variants,
        target_metric=payload.metric,
        hypothesis=None,
        baseline_metric=0.02,
        avg_cpm=None,
        avg_daily_impressions=None,
    )
    return plan


@tool
def get_test_recommendations(brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return top recommended A/B tests from profile recommendations."""
    with sync_session() as session:
        row = session.scalar(
            select(BrandProfile)
            .where(BrandProfile.brand_id == brand_id, BrandProfile.audience_segment == "all")
            .order_by(BrandProfile.computed_at.desc())
        )
        if row is None:
            return []
        recs = [
            r
            for r in (row.profile_data or {}).get("recommendations", [])
            if r.get("type") == "ab_test_candidate"
        ]
        recs.sort(key=lambda rec: float(rec.get("impact_priority", 0.0)), reverse=True)
        return recs[:3]
