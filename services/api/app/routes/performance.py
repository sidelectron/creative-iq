"""Ad performance metrics (daily upserts)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.db import Ad, AdPerformance
from shared.models.enums import BrandRole
from shared.models.schemas import (
    AdPerformanceBulkCreate,
    AdPerformanceBulkResult,
    AdPerformanceCreate,
    AdPerformanceResponse,
    ad_performance_response_from_model,
)
from shared.utils.db import get_db
from services.api.app.dependencies import require_ad_brand_role

router = APIRouter(tags=["performance"])


@router.post(
    "/{ad_id}/performance",
    response_model=AdPerformanceResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_performance(
    ad_id: uuid.UUID,
    body: AdPerformanceCreate,
    _: Ad = Depends(require_ad_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> AdPerformanceResponse:
    result = await db.execute(
        select(AdPerformance).where(AdPerformance.ad_id == ad_id, AdPerformance.date == body.date)
    )
    row = result.scalar_one_or_none()
    meta = body.metadata if body.metadata is not None else {}
    if row:
        row.impressions = body.impressions
        row.clicks = body.clicks
        row.conversions = body.conversions
        row.spend = body.spend
        row.revenue = body.revenue
        row.video_views = body.video_views
        row.video_completions = body.video_completions
        row.engagement_count = body.engagement_count
        row.perf_metadata = meta
    else:
        row = AdPerformance(
            ad_id=ad_id,
            date=body.date,
            impressions=body.impressions,
            clicks=body.clicks,
            conversions=body.conversions,
            spend=body.spend,
            revenue=body.revenue,
            video_views=body.video_views,
            video_completions=body.video_completions,
            engagement_count=body.engagement_count,
            perf_metadata=meta,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return ad_performance_response_from_model(row)


@router.post("/{ad_id}/performance/bulk", response_model=AdPerformanceBulkResult)
async def bulk_upsert_performance(
    ad_id: uuid.UUID,
    body: AdPerformanceBulkCreate,
    _: Ad = Depends(require_ad_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> AdPerformanceBulkResult:
    count = 0
    for rec in body.records:
        result = await db.execute(
            select(AdPerformance).where(
                AdPerformance.ad_id == ad_id,
                AdPerformance.date == rec.date,
            )
        )
        row = result.scalar_one_or_none()
        meta = rec.metadata if rec.metadata is not None else {}
        if row:
            row.impressions = rec.impressions
            row.clicks = rec.clicks
            row.conversions = rec.conversions
            row.spend = rec.spend
            row.revenue = rec.revenue
            row.video_views = rec.video_views
            row.video_completions = rec.video_completions
            row.engagement_count = rec.engagement_count
            row.perf_metadata = meta
        else:
            db.add(
                AdPerformance(
                    ad_id=ad_id,
                    date=rec.date,
                    impressions=rec.impressions,
                    clicks=rec.clicks,
                    conversions=rec.conversions,
                    spend=rec.spend,
                    revenue=rec.revenue,
                    video_views=rec.video_views,
                    video_completions=rec.video_completions,
                    engagement_count=rec.engagement_count,
                    perf_metadata=meta,
                )
            )
        count += 1
    await db.commit()
    return AdPerformanceBulkResult(count=count)


@router.get("/{ad_id}/performance", response_model=list[AdPerformanceResponse])
async def list_performance(
    ad_id: uuid.UUID,
    _: Ad = Depends(require_ad_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> list[AdPerformanceResponse]:
    result = await db.execute(
        select(AdPerformance)
        .where(AdPerformance.ad_id == ad_id)
        .order_by(AdPerformance.date.asc())
    )
    rows = result.scalars().all()
    return [ad_performance_response_from_model(r) for r in rows]
