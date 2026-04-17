"""Brand event CRUD and embedding lifecycle."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from shared.models.db import BrandEra, BrandEvent
from shared.models.enums import EventSource
from shared.utils.gemini import embed_text

ERA_CREATING_TYPES = {"product_launch", "positioning_shift", "agency_change"}


def _event_embedding_text(title: str, description: str | None, impact_tags: list[str]) -> str:
    pieces = [title.strip()]
    if description:
        pieces.append(description.strip())
    if impact_tags:
        pieces.append("tags: " + ", ".join(sorted(impact_tags)))
    return " | ".join(p for p in pieces if p)


def _is_era_creating(event_type: str, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return event_type in ERA_CREATING_TYPES


def create_event(
    session: Session,
    *,
    brand_id: uuid.UUID,
    event_type: str,
    title: str,
    event_date: datetime,
    description: str | None,
    impact_tags: list[str],
    source: str = EventSource.USER_PROVIDED.value,
    is_era_creating: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrandEvent:
    payload = dict(metadata or {})
    payload["is_era_creating"] = _is_era_creating(event_type, is_era_creating)
    embedding = embed_text(
        text=_event_embedding_text(title=title, description=description, impact_tags=impact_tags)
    )
    row = BrandEvent(
        brand_id=brand_id,
        event_type=event_type,
        title=title,
        description=description,
        source=source,
        event_date=event_date.astimezone(timezone.utc),
        impact_tags=impact_tags,
        event_metadata=payload,
        embedding=embedding,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_user_event(
    session: Session,
    *,
    brand_id: uuid.UUID,
    event_id: uuid.UUID,
    update_payload: dict[str, Any],
) -> BrandEvent | None:
    row = session.scalar(
        select(BrandEvent).where(BrandEvent.id == event_id, BrandEvent.brand_id == brand_id)
    )
    if row is None or row.source != EventSource.USER_PROVIDED.value:
        return None
    for key in ("title", "description", "event_date", "impact_tags"):
        if key in update_payload and update_payload[key] is not None:
            setattr(row, key, update_payload[key])
    if "is_era_creating" in update_payload and update_payload["is_era_creating"] is not None:
        meta = dict(row.event_metadata or {})
        meta["is_era_creating"] = bool(update_payload["is_era_creating"])
        row.event_metadata = meta
    row.embedding = embed_text(
        text=_event_embedding_text(
            title=row.title,
            description=row.description,
            impact_tags=[str(v) for v in (row.impact_tags or [])],
        )
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def delete_user_event(session: Session, *, brand_id: uuid.UUID, event_id: uuid.UUID) -> bool:
    row = session.scalar(
        select(BrandEvent).where(BrandEvent.id == event_id, BrandEvent.brand_id == brand_id)
    )
    if row is None or row.source != EventSource.USER_PROVIDED.value:
        return False
    session.delete(row)
    session.commit()
    return True


def list_events(
    session: Session,
    *,
    brand_id: uuid.UUID,
    event_type: str | None,
    source: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[BrandEvent], int]:
    conditions = [BrandEvent.brand_id == brand_id]
    if event_type:
        conditions.append(BrandEvent.event_type == event_type)
    if source:
        conditions.append(BrandEvent.source == source)
    if start_date:
        conditions.append(BrandEvent.event_date >= start_date)
    if end_date:
        conditions.append(BrandEvent.event_date <= end_date)
    stmt = select(BrandEvent).where(and_(*conditions))
    total = len(list(session.scalars(stmt).all()))
    offset = (page - 1) * page_size
    rows = list(
        session.scalars(
            stmt.order_by(BrandEvent.event_date.desc(), BrandEvent.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return rows, total


def find_active_era_for_event(session: Session, *, brand_id: uuid.UUID, event_date: datetime) -> BrandEra | None:
    eras = session.scalars(
        select(BrandEra).where(BrandEra.brand_id == brand_id).order_by(BrandEra.start_date.desc())
    ).all()
    for era in eras:
        end = era.end_date or datetime.max.replace(tzinfo=timezone.utc)
        if era.start_date <= event_date <= end:
            return era
    return None
