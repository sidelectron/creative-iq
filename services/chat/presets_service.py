"""Industry presets service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from shared.models.db import IndustryPreset


def list_presets(session: Session) -> list[IndustryPreset]:
    return list(
        session.scalars(
            select(IndustryPreset).order_by(IndustryPreset.industry.asc(), IndustryPreset.platform.asc())
        ).all()
    )


def get_preset(session: Session, *, industry: str) -> list[IndustryPreset]:
    return list(
        session.scalars(
            select(IndustryPreset).where(IndustryPreset.industry == industry).order_by(IndustryPreset.platform.asc())
        ).all()
    )


def update_from_data(session: Session, *, industry: str) -> list[IndustryPreset]:
    # Conservative update path: refresh timestamp marker, preserve existing baseline profile.
    rows = get_preset(session, industry=industry)
    now = datetime.now(timezone.utc).isoformat()
    updated: list[IndustryPreset] = []
    for row in rows:
        payload: dict[str, Any] = dict(row.baseline_profile or {})
        payload["last_refreshed_at"] = now
        row.baseline_profile = payload
        session.add(row)
        updated.append(row)
    if not updated:
        fallback = session.scalar(
            select(IndustryPreset).where(
                and_(IndustryPreset.industry == "all_industries", IndustryPreset.audience_segment == "all")
            )
        )
        if fallback is not None:
            created = IndustryPreset(
                industry=industry,
                platform=fallback.platform,
                audience_segment="all",
                baseline_profile=dict(fallback.baseline_profile or {}),
                description=f"Bootstrapped from all_industries at {now}",
            )
            session.add(created)
            updated.append(created)
    session.commit()
    return updated
