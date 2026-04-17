"""Phase 5 event + semantic memory routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from shared.celery_app import celery_app
from services.api.app.dependencies import get_current_active_user, require_brand_role
from services.chat import era_service, events_service, impact_analysis_service, memory_search
from shared.models.db import Ad, BrandEvent, BrandProfile
from shared.models.enums import BrandRole
from shared.models.schemas import (
    EventCreateBody,
    EventImpactRequest,
    EventImpactResponse,
    EventResponse,
    EventSearchBody,
    EventSearchResult,
    EventUpdateBody,
    PaginatedResponse,
)
from shared.utils.db_sync import sync_session

router = APIRouter(prefix="/brands", tags=["events"])


def _dispatch_profile_recompute_for_brand_platforms(session, brand_id: uuid.UUID) -> None:
    platforms = {
        str(p)
        for p in session.scalars(
            select(Ad.platform).where(Ad.brand_id == brand_id, Ad.deleted_at.is_(None))
        ).all()
        if p
    }
    platforms.update(
        {
            str(p)
            for p in session.scalars(select(BrandProfile.platform).where(BrandProfile.brand_id == brand_id)).all()
            if p
        }
    )
    for platform in sorted(platforms):
        celery_app.send_task(
            "services.profile_engine.tasks.profile_tasks.compute_profile",
            args=[str(brand_id), platform],
            queue="profile",
        )


def _event_response(row) -> EventResponse:
    return EventResponse(
        id=row.id,
        brand_id=row.brand_id,
        event_type=row.event_type,
        title=row.title,
        description=row.description,
        source=row.source,
        event_date=row.event_date,
        impact_tags=list(row.impact_tags or []),
        metadata=dict(row.event_metadata or {}),
        created_at=row.created_at,
    )


@router.post("/{brand_id}/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_brand_event(
    brand_id: uuid.UUID,
    body: EventCreateBody,
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
) -> EventResponse:
    with sync_session() as session:
        row = events_service.create_event(
            session,
            brand_id=brand_id,
            event_type=body.event_type,
            title=body.title,
            event_date=body.event_date,
            description=body.description,
            impact_tags=body.impact_tags,
            is_era_creating=body.is_era_creating,
        )
        new_era = era_service.maybe_create_new_era(session, event=row)
        if new_era is not None:
            _dispatch_profile_recompute_for_brand_platforms(session, brand_id)
        return _event_response(row)


@router.get("/{brand_id}/events", response_model=PaginatedResponse[EventResponse])
async def list_brand_events(
    brand_id: uuid.UUID,
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
) -> PaginatedResponse[EventResponse]:
    with sync_session() as session:
        rows, total = events_service.list_events(
            session,
            brand_id=brand_id,
            event_type=event_type,
            source=source,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
        return PaginatedResponse(
            items=[_event_response(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/{brand_id}/events/{event_id}", response_model=EventResponse)
async def get_brand_event(
    brand_id: uuid.UUID,
    event_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
) -> EventResponse:
    with sync_session() as session:
        row = session.scalar(
            select(BrandEvent).where(
                BrandEvent.id == event_id,
                BrandEvent.brand_id == brand_id,
            )
        )
        if row is not None:
            return _event_response(row)
    raise HTTPException(status_code=404, detail="Event not found")


@router.patch("/{brand_id}/events/{event_id}", response_model=EventResponse)
async def patch_brand_event(
    brand_id: uuid.UUID,
    event_id: uuid.UUID,
    body: EventUpdateBody,
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
) -> EventResponse:
    with sync_session() as session:
        row = events_service.update_user_event(
            session,
            brand_id=brand_id,
            event_id=event_id,
            update_payload=body.model_dump(exclude_none=True),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Event not found or not editable")
        era_service.recompute_eras(session, brand_id=brand_id)
        _dispatch_profile_recompute_for_brand_platforms(session, brand_id)
        return _event_response(row)


@router.delete("/{brand_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand_event(
    brand_id: uuid.UUID,
    event_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
) -> None:
    with sync_session() as session:
        ok = events_service.delete_user_event(session, brand_id=brand_id, event_id=event_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Event not found or not editable")
        era_service.recompute_eras(session, brand_id=brand_id)
        _dispatch_profile_recompute_for_brand_platforms(session, brand_id)


@router.post("/{brand_id}/events/search", response_model=list[EventSearchResult])
async def search_brand_events(
    brand_id: uuid.UUID,
    body: EventSearchBody,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
) -> list[EventSearchResult]:
    with sync_session() as session:
        rows = memory_search.search_events(
            session,
            brand_id=brand_id,
            query=body.query,
            top_k=body.top_k,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        return [EventSearchResult(**row) for row in rows]


@router.post("/{brand_id}/events/{event_id}/analyze-impact", response_model=EventImpactResponse)
async def analyze_impact(
    brand_id: uuid.UUID,
    event_id: uuid.UUID,
    body: EventImpactRequest,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
) -> EventImpactResponse:
    with sync_session() as session:
        payload = impact_analysis_service.analyze_event_impact(
            session,
            brand_id=brand_id,
            event_id=event_id,
            pre_days=body.pre_days,
            post_days=body.post_days,
            force_recompute=body.force_recompute,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return EventImpactResponse(
            event_id=event_id,
            summary=str(payload["summary"]),
            pre_window=dict(payload["pre_window"]),
            post_window=dict(payload["post_window"]),
            deltas=dict(payload["deltas"]),
            significance=dict(payload["significance"]),
            cached=bool(payload.get("cached", False)),
        )


def require_admin_user(user=Depends(get_current_active_user)):
    from shared.config.settings import settings

    admins = set(settings.admin_email_list())
    if user.email.lower() not in admins:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
