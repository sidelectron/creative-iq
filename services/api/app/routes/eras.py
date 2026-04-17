"""Era management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from shared.celery_app import celery_app
from services.api.app.dependencies import require_brand_role
from services.chat import era_service
from shared.models.db import Ad, BrandEra, BrandProfile
from shared.models.enums import BrandRole
from shared.models.schemas import EraResponse
from shared.utils.db_sync import sync_session

router = APIRouter(prefix="/brands", tags=["eras"])


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


@router.get("/{brand_id}/eras", response_model=list[EraResponse])
async def list_eras(
    brand_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
) -> list[EraResponse]:
    with sync_session() as session:
        rows = list(
            session.scalars(
                select(BrandEra)
                .where(BrandEra.brand_id == brand_id)
                .order_by(BrandEra.start_date.asc())
            ).all()
        )
        if not rows:
            founding = era_service.ensure_founding_era(session, brand_id=brand_id)
            rows = [founding]
        output: list[EraResponse] = []
        for row in rows:
            stats = era_service.era_stats(session, era=row)
            output.append(
                EraResponse(
                    id=row.id,
                    era_name=row.era_name,
                    start_date=row.start_date,
                    end_date=row.end_date,
                    triggering_event_id=row.triggering_event_id,
                    context_summary=row.context_summary,
                    ads_count=int(stats["ads_count"]),
                    average_performance=dict(stats["average_performance"]),
                )
            )
        return output


@router.post("/{brand_id}/eras/recompute", response_model=list[EraResponse])
async def recompute_eras(
    brand_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
) -> list[EraResponse]:
    with sync_session() as session:
        rows = era_service.recompute_eras(session, brand_id=brand_id)
        _dispatch_profile_recompute_for_brand_platforms(session, brand_id)
        out: list[EraResponse] = []
        for row in rows:
            stats = era_service.era_stats(session, era=row)
            out.append(
                EraResponse(
                    id=row.id,
                    era_name=row.era_name,
                    start_date=row.start_date,
                    end_date=row.end_date,
                    triggering_event_id=row.triggering_event_id,
                    context_summary=row.context_summary,
                    ads_count=int(stats["ads_count"]),
                    average_performance=dict(stats["average_performance"]),
                )
            )
        return out
