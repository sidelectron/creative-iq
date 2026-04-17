"""Phase 4 profile, A/B, and drift routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.celery_app import celery_app
from shared.models.db import ABTest, BrandEvent, BrandMember, BrandProfile
from shared.models.enums import BrandRole
from shared.models.schemas import (
    ABTestAssignAdsBody,
    ABTestCreateBody,
    ABTestDesignPreviewResponse,
    ABTestResponse,
    ABTestStatusPatchBody,
    DriftAlertResponse,
    ProfileAttributeResponse,
    ProfileComputeResponse,
    ProfileRecommendationsResponse,
    ProfileResponse,
    PaginatedResponse,
)
from shared.utils.db import get_db
from shared.utils.redis_client import cache_get, cache_set
from shared.utils.db_sync import sync_session
from services.ab_testing.analyzer import analyze_test
from services.ab_testing.designer import design_test, persist_test_plan
from services.api.app.dependencies import get_current_active_user, require_brand_role
from services.chat.auto_events_service import emit_ab_lifecycle_event

router = APIRouter(prefix="/brands", tags=["profile-ab"])


@router.post("/{brand_id}/profile/compute", response_model=ProfileComputeResponse)
async def compute_profile(
    brand_id: uuid.UUID,
    platform: str = Query(...),
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
) -> ProfileComputeResponse:
    result = celery_app.send_task(
        "services.profile_engine.tasks.profile_tasks.compute_profile",
        args=[str(brand_id), platform],
        queue="profile",
    )
    profile = result.get(timeout=180)
    return ProfileComputeResponse(status="computed", profile=profile)


@router.get("/{brand_id}/profile", response_model=ProfileResponse)
async def get_profile(
    brand_id: uuid.UUID,
    platform: str | None = Query(None),
    metric: str | None = Query(None),
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    platform_payload: dict[str, Any] = {}
    if platform is not None:
        platforms = [platform]
    else:
        rows = list(
            (
                await db.scalars(
                    select(BrandProfile.platform).where(
                        BrandProfile.brand_id == brand_id,
                        BrandProfile.audience_segment == "all",
                    )
                )
            ).all()
        )
        platforms = [str(p) for p in rows]
    for selected_platform in platforms:
        key = f"brand_profile:{brand_id}:{selected_platform}"
        cached = await cache_get(key)
        data: dict[str, Any] | None = json.loads(cached) if cached else None
        if data is None:
            row = await db.scalar(
                select(BrandProfile).where(
                    BrandProfile.brand_id == brand_id,
                    BrandProfile.platform == selected_platform,
                    BrandProfile.audience_segment == "all",
                )
            )
            if row is None:
                continue
            data = dict(row.profile_data or {})
            await cache_set(key, json.dumps(data, default=str), 3600)
        if metric:
            data["metric"] = metric
        platform_payload[selected_platform] = data
    if not platform_payload:
        raise HTTPException(status_code=404, detail="Profile not found")
    first_profile = next(iter(platform_payload.values()))
    highlights = list(first_profile.get("recommendations", []))[:3]
    total_attrs = sum(len(v) for v in (first_profile.get("categorical", {}) or {}).values())
    confident_attrs = 0
    for values in (first_profile.get("categorical", {}) or {}).values():
        for payload in values.values():
            if float(payload.get("confidence", 0)) >= 0.7:
                confident_attrs += 1
    coverage = (confident_attrs / total_attrs) if total_attrs else 0.0
    data_health = {
        "total_ads_analyzed": int(first_profile.get("total_ads_analyzed", 0)),
        "computed_at": first_profile.get("computed_at"),
        "freshness_seconds": max(
            0,
            int(
                (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(first_profile["computed_at"])
                ).total_seconds()
            )
            if first_profile.get("computed_at")
            else 0,
        ),
        "coverage_high_confidence": coverage,
    }
    recent_events = list(
        (
            await db.scalars(
                select(BrandEvent)
                .where(BrandEvent.brand_id == brand_id)
                .order_by(BrandEvent.event_date.desc())
                .limit(3)
            )
        ).all()
    )
    current_era = await db.scalar(
        select(BrandEvent)
        .where(
            BrandEvent.brand_id == brand_id,
            BrandEvent.event_metadata["is_era_creating"].astext == "true",
        )
        .order_by(BrandEvent.event_date.desc())
    )
    profile_payload = first_profile if platform is not None else {"platforms": platform_payload}
    profile_payload["context"] = {
        "recent_events": [
            {
                "event_id": str(row.id),
                "title": row.title,
                "event_type": row.event_type,
                "event_date": row.event_date.isoformat(),
            }
            for row in recent_events
        ],
        "current_era_hint": {
            "trigger_event_id": str(current_era.id),
            "title": current_era.title,
        }
        if current_era is not None
        else None,
        "score_change_explanations": [
            {
                "type": "threshold_change",
                "threshold": 0.10,
                "message": "Attributes with score deltas above 10% are highlighted via event memory search.",
            }
        ],
    }
    return ProfileResponse(profile=profile_payload, highlights=highlights, data_health=data_health)


@router.get("/{brand_id}/profile/attribute/{attribute_name}", response_model=ProfileAttributeResponse)
async def get_profile_attribute(
    brand_id: uuid.UUID,
    attribute_name: str,
    platform: str = Query(...),
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> ProfileAttributeResponse:
    row = await db.scalar(
        select(BrandProfile).where(
            BrandProfile.brand_id == brand_id,
            BrandProfile.platform == platform,
            BrandProfile.audience_segment == "all",
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    values = (row.profile_data or {}).get("categorical", {}).get(attribute_name)
    if not values:
        raise HTTPException(status_code=404, detail="Attribute not found")
    recommended = sorted(
        values.items(), key=lambda item: float(item[1].get("score", 0.0)), reverse=True
    )[0][0]
    return ProfileAttributeResponse(
        attribute_name=attribute_name,
        values=values,
        trend=[],
        recommended_value=recommended,
    )


@router.get(
    "/{brand_id}/profile/recommendations",
    response_model=ProfileRecommendationsResponse,
)
async def get_profile_recommendations(
    brand_id: uuid.UUID,
    platform: str | None = Query(None),
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> ProfileRecommendationsResponse:
    stmt = select(BrandProfile).where(
        BrandProfile.brand_id == brand_id,
        BrandProfile.audience_segment == "all",
    )
    if platform is not None:
        stmt = stmt.where(BrandProfile.platform == platform)
    row = await db.scalar(stmt.order_by(BrandProfile.computed_at.desc()))
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    recs = list((row.profile_data or {}).get("recommendations", []))
    return ProfileRecommendationsResponse(recommendations=recs)


@router.post(
    "/{brand_id}/tests/preview-design",
    response_model=ABTestDesignPreviewResponse,
)
async def preview_ab_test_design(
    brand_id: uuid.UUID,
    body: ABTestCreateBody,
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    user=Depends(get_current_active_user),
) -> ABTestDesignPreviewResponse:
    """Return sample size / budget / duration estimates without persisting a test."""
    baseline = float(body.baseline_metric or 0.02)
    avg_cpm = float(body.avg_cpm) if body.avg_cpm is not None else None
    avg_daily_impressions = (
        float(body.avg_daily_impressions) if body.avg_daily_impressions is not None else None
    )
    plan = design_test(
        brand_id=brand_id,
        created_by=user.id,
        attribute_to_test=body.attribute_to_test,
        variants=body.variants,
        target_metric=body.target_metric,
        hypothesis=body.hypothesis,
        baseline_metric=baseline,
        avg_cpm=avg_cpm,
        avg_daily_impressions=avg_daily_impressions,
    )
    budget = plan.get("estimated_budget_per_variant")
    return ABTestDesignPreviewResponse(
        sample_size_per_variant=int(plan["sample_size_per_variant"]),
        estimated_budget_per_variant=float(budget) if budget is not None else None,
        estimated_duration_days=plan.get("estimated_duration_days"),
        hypothesis=str(plan["hypothesis"]),
        alpha=float(plan["alpha"]),
        power=float(plan["power"]),
        mde_relative=float(plan["mde_relative"]),
        mde_absolute=float(plan["mde_absolute"]),
    )


@router.post("/{brand_id}/tests", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test(
    brand_id: uuid.UUID,
    body: ABTestCreateBody,
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    baseline = float(body.baseline_metric or 0.02)
    avg_cpm = float(body.avg_cpm) if body.avg_cpm is not None else None
    avg_daily_impressions = (
        float(body.avg_daily_impressions) if body.avg_daily_impressions is not None else None
    )
    plan = design_test(
        brand_id=brand_id,
        created_by=user.id,
        attribute_to_test=body.attribute_to_test,
        variants=body.variants,
        target_metric=body.target_metric,
        hypothesis=body.hypothesis,
        baseline_metric=baseline,
        avg_cpm=avg_cpm,
        avg_daily_impressions=avg_daily_impressions,
    )
    with sync_session() as session:
        saved = persist_test_plan(
            session,
            brand_id=brand_id,
            created_by=user.id,
            attribute_to_test=body.attribute_to_test,
            target_metric=body.target_metric,
            plan=plan,
        )
    return ABTestResponse.model_validate(saved, from_attributes=True)


@router.get("/{brand_id}/tests", response_model=PaginatedResponse[ABTestResponse])
async def list_ab_tests(
    brand_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ABTestResponse]:
    stmt = select(ABTest).where(ABTest.brand_id == brand_id)
    if status_filter:
        stmt = stmt.where(ABTest.status == status_filter)
    total = len(list((await db.scalars(stmt)).all()))
    offset = (page - 1) * page_size
    tests = list(
        (
            await db.scalars(
                stmt.order_by(ABTest.created_at.desc()).offset(offset).limit(page_size)
            )
        ).all()
    )
    items = [ABTestResponse.model_validate(t, from_attributes=True) for t in tests]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{brand_id}/tests/{test_id}", response_model=ABTestResponse)
async def get_ab_test(
    brand_id: uuid.UUID,
    test_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    row = await db.scalar(select(ABTest).where(ABTest.id == test_id, ABTest.brand_id == brand_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return ABTestResponse.model_validate(row, from_attributes=True)


@router.patch("/{brand_id}/tests/{test_id}", response_model=ABTestResponse)
async def patch_ab_test_status(
    brand_id: uuid.UUID,
    test_id: uuid.UUID,
    body: ABTestStatusPatchBody,
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    row = await db.scalar(select(ABTest).where(ABTest.id == test_id, ABTest.brand_id == brand_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    allowed = {
        "proposed": {"active", "cancelled"},
        "active": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    if body.status not in allowed.get(row.status, set()):
        raise HTTPException(status_code=409, detail="Invalid status transition")
    row.status = body.status
    if body.status == "active":
        row.started_at = datetime.now(timezone.utc)
        with sync_session() as session:
            sync_row = session.get(ABTest, test_id)
            if sync_row is not None:
                emit_ab_lifecycle_event(session, test=sync_row, status="active")
    await db.commit()
    if body.status == "completed":
        with sync_session() as session:
            sync_row = session.get(ABTest, test_id)
            if sync_row is not None:
                analyze_test(session, sync_row)
                celery_app.send_task(
                    "services.profile_engine.tasks.profile_tasks.compute_profile",
                    args=[str(brand_id), body.platform],
                    queue="profile",
                )
        await db.refresh(row)
    return ABTestResponse.model_validate(row, from_attributes=True)


@router.post("/{brand_id}/tests/{test_id}/assign-ads", response_model=ABTestResponse)
async def assign_ab_test_ads(
    brand_id: uuid.UUID,
    test_id: uuid.UUID,
    body: ABTestAssignAdsBody,
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> ABTestResponse:
    row = await db.scalar(select(ABTest).where(ABTest.id == test_id, ABTest.brand_id == brand_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    variants = list(row.variants or [])
    mapped: list[dict[str, Any]] = []
    for name in variants:
        key = name if isinstance(name, str) else str(name.get("name", "variant"))
        mapped.append({"name": key, "ad_ids": [str(aid) for aid in body.assignments.get(key, [])]})
    row.variants = mapped
    await db.commit()
    return ABTestResponse.model_validate(row, from_attributes=True)


@router.get("/{brand_id}/tests/recommendations", response_model=ProfileRecommendationsResponse)
async def ab_test_recommendations(
    brand_id: uuid.UUID,
    platform: str | None = Query(None),
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> ProfileRecommendationsResponse:
    stmt = select(BrandProfile).where(
        BrandProfile.brand_id == brand_id,
        BrandProfile.audience_segment == "all",
    )
    if platform is not None:
        stmt = stmt.where(BrandProfile.platform == platform)
    row = await db.scalar(stmt.order_by(BrandProfile.computed_at.desc()))
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    recs = [
        r
        for r in (row.profile_data or {}).get("recommendations", [])
        if r.get("type") == "ab_test_candidate"
    ]
    recs.sort(
        key=lambda rec: float(rec.get("impact_priority", 0.0)),
        reverse=True,
    )
    return ProfileRecommendationsResponse(recommendations=recs[:3])


@router.get("/{brand_id}/drift", response_model=list[DriftAlertResponse])
async def get_drift(
    brand_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> list[DriftAlertResponse]:
    rows = list(
        (
            await db.scalars(
                select(BrandEvent).where(
                    BrandEvent.brand_id == brand_id,
                    BrandEvent.event_type == "performance_anomaly",
                    BrandEvent.source == "auto_detected",
                )
            )
        ).all()
    )
    return [
        DriftAlertResponse(
            event_id=row.id,
            event_date=row.event_date,
            attribute_key=str((row.event_metadata or {}).get("attribute_key", "")),
            historical_score=float((row.event_metadata or {}).get("historical_score", 0.0)),
            recent_score=float((row.event_metadata or {}).get("recent_score", 0.0)),
            direction=str((row.event_metadata or {}).get("direction", "unknown")),
            magnitude_relative=float((row.event_metadata or {}).get("magnitude_relative", 0.0)),
            recent_sample_size=int((row.event_metadata or {}).get("recent_sample_size", 0)),
        )
        for row in rows
    ]
