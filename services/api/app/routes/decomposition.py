"""Ad-scoped decomposition routes under /api/v1/ads (no brand_id in path)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.celery_app import celery_app
from shared.models.db import Ad, CreativeFingerprint
from shared.models.enums import AdStatus, BrandRole
from shared.models.schemas import AdDecompositionStatusResponse, CreativeFingerprintResponse
from shared.utils.db import get_db
from services.api.app.dependencies import require_ad_brand_role

router = APIRouter(tags=["decomposition"])


@router.post("/{ad_id}/decompose", status_code=status.HTTP_202_ACCEPTED)
async def manual_decompose(
    ad_id: uuid.UUID,
    ad: Ad = Depends(require_ad_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if ad.status == AdStatus.DECOMPOSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ad is already decomposing",
        )
    if ad.status not in (
        AdStatus.INGESTED.value,
        AdStatus.FAILED.value,
        AdStatus.DECOMPOSED.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ad cannot be decomposed from this state",
        )
    celery_app.send_task(
        "services.decomposition.tasks.decompose_ad",
        args=[str(ad_id)],
        queue="decomposition",
    )
    return {"status": "queued", "ad_id": str(ad_id)}


@router.get("/{ad_id}/fingerprint", response_model=CreativeFingerprintResponse)
async def get_fingerprint(
    ad_id: uuid.UUID,
    ad: Ad = Depends(require_ad_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> CreativeFingerprintResponse:
    if ad.status != AdStatus.DECOMPOSED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fingerprint not available",
        )
    result = await db.execute(
        select(CreativeFingerprint).where(CreativeFingerprint.ad_id == ad_id)
    )
    fp = result.scalar_one_or_none()
    if fp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fingerprint not found")
    return CreativeFingerprintResponse(
        id=fp.id,
        ad_id=fp.ad_id,
        attributes=fp.attributes,
        low_level_features=fp.low_level_features,
        gemini_analysis=fp.gemini_analysis,
        transcript=fp.transcript,
        gemini_model_used=fp.gemini_model_used,
        gemini_tokens_input=fp.gemini_tokens_input,
        gemini_tokens_output=fp.gemini_tokens_output,
        processing_duration_seconds=fp.processing_duration_seconds,
        created_at=fp.created_at,
    )


@router.get("/{ad_id}/status", response_model=AdDecompositionStatusResponse)
async def get_decomposition_status(
    ad_id: uuid.UUID,
    ad: Ad = Depends(require_ad_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> AdDecompositionStatusResponse:
    await db.refresh(ad)
    return AdDecompositionStatusResponse(status=ad.status, progress=None)
