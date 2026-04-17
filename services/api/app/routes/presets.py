"""Industry presets routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from services.api.app.dependencies import get_current_active_user
from services.chat import presets_service
from shared.models.schemas import PresetResponse
from shared.utils.db_sync import sync_session

router = APIRouter(tags=["presets"])


def _require_admin_user(user=Depends(get_current_active_user)):
    from shared.config.settings import settings

    if user.email.lower() not in set(settings.admin_email_list()):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


@router.get("/presets", response_model=list[PresetResponse])
async def list_presets() -> list[PresetResponse]:
    with sync_session() as session:
        rows = presets_service.list_presets(session)
        return [
            PresetResponse(
                industry=row.industry,
                platform=row.platform,
                audience_segment=row.audience_segment,
                baseline_profile=dict(row.baseline_profile or {}),
                description=row.description,
            )
            for row in rows
        ]


@router.get("/presets/{industry}", response_model=list[PresetResponse])
async def get_presets_for_industry(industry: str) -> list[PresetResponse]:
    with sync_session() as session:
        rows = presets_service.get_preset(session, industry=industry)
        return [
            PresetResponse(
                industry=row.industry,
                platform=row.platform,
                audience_segment=row.audience_segment,
                baseline_profile=dict(row.baseline_profile or {}),
                description=row.description,
            )
            for row in rows
        ]


@router.post("/presets/{industry}/update-from-data", response_model=list[PresetResponse])
async def update_preset_from_data(
    industry: str,
    _: object = Depends(_require_admin_user),
) -> list[PresetResponse]:
    with sync_session() as session:
        rows = presets_service.update_from_data(session, industry=industry)
        return [
            PresetResponse(
                industry=row.industry,
                platform=row.platform,
                audience_segment=row.audience_segment,
                baseline_profile=dict(row.baseline_profile or {}),
                description=row.description,
            )
            for row in rows
        ]
