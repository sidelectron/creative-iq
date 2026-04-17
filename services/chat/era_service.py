"""Era lifecycle management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from shared.models.db import Ad, AdPerformance, Brand, BrandEra, BrandEvent
from shared.utils.gemini import GeminiError, generate_json


def ensure_founding_era(session: Session, *, brand_id: uuid.UUID) -> BrandEra:
    existing = session.scalar(
        select(BrandEra).where(BrandEra.brand_id == brand_id).order_by(BrandEra.start_date.asc())
    )
    if existing is not None:
        return existing
    brand = session.get(Brand, brand_id)
    start = brand.created_at if brand is not None else datetime.now(timezone.utc)
    era = BrandEra(
        brand_id=brand_id,
        era_name="Founding Era",
        start_date=start,
        context_summary="Initial baseline era.",
    )
    session.add(era)
    session.commit()
    session.refresh(era)
    return era


def maybe_create_new_era(
    session: Session,
    *,
    event: BrandEvent,
) -> BrandEra | None:
    meta = dict(event.event_metadata or {})
    if not bool(meta.get("is_era_creating")):
        return None
    current = session.scalar(
        select(BrandEra)
        .where(BrandEra.brand_id == event.brand_id, BrandEra.end_date.is_(None))
        .order_by(BrandEra.start_date.desc())
    )
    if current is None:
        ensure_founding_era(session, brand_id=event.brand_id)
        current = session.scalar(
            select(BrandEra)
            .where(BrandEra.brand_id == event.brand_id, BrandEra.end_date.is_(None))
            .order_by(BrandEra.start_date.desc())
        )
    if current and current.start_date >= event.event_date:
        return None
    if current:
        current.end_date = event.event_date
        session.add(current)
    era_name, summary = _generate_era_name_and_summary(event)
    new_era = BrandEra(
        brand_id=event.brand_id,
        era_name=era_name,
        start_date=event.event_date,
        triggering_event_id=event.id,
        context_summary=summary,
    )
    session.add(new_era)
    session.commit()
    session.refresh(new_era)
    return new_era


def recompute_eras(session: Session, *, brand_id: uuid.UUID) -> list[BrandEra]:
    # Rebuild chronologically from era-creating events.
    existing = list(session.scalars(select(BrandEra).where(BrandEra.brand_id == brand_id)).all())
    for row in existing:
        session.delete(row)
    session.commit()
    ensure_founding_era(session, brand_id=brand_id)
    events = list(
        session.scalars(
            select(BrandEvent)
            .where(BrandEvent.brand_id == brand_id)
            .order_by(BrandEvent.event_date.asc())
        ).all()
    )
    for event in events:
        maybe_create_new_era(session, event=event)
    return list(
        session.scalars(
            select(BrandEra).where(BrandEra.brand_id == brand_id).order_by(BrandEra.start_date.asc())
        ).all()
    )


def era_stats(session: Session, *, era: BrandEra) -> dict[str, Any]:
    end = era.end_date or datetime.now(timezone.utc)
    ads_count = int(
        session.scalar(
            select(func.count())
            .select_from(Ad)
            .where(
                Ad.brand_id == era.brand_id,
                Ad.deleted_at.is_(None),
                or_(
                    and_(Ad.published_at.is_not(None), Ad.published_at >= era.start_date, Ad.published_at <= end),
                    and_(Ad.published_at.is_(None), Ad.created_at >= era.start_date, Ad.created_at <= end),
                ),
            )
        )
        or 0
    )
    perf_row = session.execute(
        select(
            func.avg(AdPerformance.clicks * 1.0 / func.nullif(AdPerformance.impressions, 0)).label("ctr"),
            func.avg(AdPerformance.spend).label("spend"),
            func.avg(AdPerformance.revenue).label("revenue"),
        )
        .join(Ad, Ad.id == AdPerformance.ad_id)
        .where(
            Ad.brand_id == era.brand_id,
            Ad.deleted_at.is_(None),
            AdPerformance.date >= era.start_date.date(),
            AdPerformance.date <= end.date(),
        )
    ).first()
    return {
        "ads_count": ads_count,
        "average_performance": {
            "ctr": float(perf_row.ctr or 0.0) if perf_row else 0.0,
            "spend": float(perf_row.spend or 0.0) if perf_row else 0.0,
            "revenue": float(perf_row.revenue or 0.0) if perf_row else 0.0,
        },
    }


def _generate_era_name_and_summary(event: BrandEvent) -> tuple[str, str]:
    fallback_name = f"{event.event_type.replace('_', ' ').title()} Era"
    fallback_summary = f"Era started due to {event.title}."
    try:
        payload, _, _ = generate_json(
            model="gemini-2.5-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Create concise era name and one sentence summary as JSON "
                                '{"era_name":"...","summary":"..."} for this event: '
                                f"{event.title}. Description: {event.description or ''}"
                            )
                        }
                    ],
                }
            ],
            cache_key_parts={"era_event": str(event.id)},
        )
        return (
            str(payload.get("era_name") or fallback_name)[:255],
            str(payload.get("summary") or fallback_summary)[:1000],
        )
    except GeminiError:
        return fallback_name, fallback_summary
