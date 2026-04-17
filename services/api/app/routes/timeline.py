"""Unified timeline routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from services.api.app.dependencies import require_brand_role
from services.chat import timeline_service
from shared.models.enums import BrandRole
from shared.models.schemas import PaginatedResponse, TimelineResponseItem
from shared.utils.db_sync import sync_session

router = APIRouter(prefix="/brands", tags=["timeline"])


@router.get("/{brand_id}/timeline", response_model=PaginatedResponse[TimelineResponseItem])
async def get_timeline(
    brand_id: uuid.UUID,
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
) -> PaginatedResponse[TimelineResponseItem]:
    with sync_session() as session:
        rows, total = timeline_service.list_timeline_items(
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
            items=[TimelineResponseItem(**row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
