"""Generation jobs API (Phase 7 Step 8, 10)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from uuid_utils.compat import uuid7

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.dependencies import get_current_active_user, require_brand_role
from services.chat.events_service import create_event
from services.generation.export_render import export_json, export_markdown, export_pdf
from services.generation.metrics import BRIEF_FEEDBACK_TOTAL
from services.generation.repositories import jobs as job_repo
from services.generation.schemas import (
    GenerationCreateBody,
    GenerationFeedbackBody,
    GenerationHistoryItem,
    GenerationJobCreatedResponse,
    GenerationJobStatusResponse,
    normalize_feedback_rating,
)


def _brief_chips_from_result(result: dict | None) -> tuple[str | None, str | None, str | None]:
    """Pull hook / duration / tone labels from completed job primary brief."""
    if not result:
        return None, None, None
    primary = result.get("primary_brief") or {}
    specs = primary.get("attribute_specs") or []
    hook = duration = tone = None
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name") or "").lower().strip()
        rec = str(spec.get("recommended") or "").strip()
        if not rec:
            continue
        if name == "hook_type" and hook is None:
            hook = rec[:80]
        elif name == "duration_seconds" and duration is None:
            duration = rec[:40]
        elif name in ("emotional_tone", "tone", "emotional tone") and tone is None:
            tone = rec[:80]
    return hook, duration, tone
from services.generation.tasks import run_generation_job
from shared.models.db import GenerationJob, User
from shared.models.enums import BrandRole, EventSource, EventType
from shared.models.schemas import PaginatedResponse
from shared.utils.db import get_db
from shared.utils.db_sync import sync_session

log = structlog.get_logger()

router = APIRouter(prefix="/brands", tags=["generation"])


@router.post(
    "/{brand_id}/generate",
    response_model=GenerationJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_generation(
    brand_id: uuid.UUID,
    body: GenerationCreateBody,
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobCreatedResponse:
    from services.generation.context import resolve_primary_platform

    job_id = uuid7()
    req = body.model_dump(mode="json")
    plat = body.platform or await resolve_primary_platform(db, brand_id=brand_id)
    req["platform"] = plat
    await job_repo.create_job(
        db,
        job_id=job_id,
        brand_id=brand_id,
        user_id=current_user.id,
        request_json=req,
        celery_task_id=None,
    )
    async_result = run_generation_job.delay(str(job_id))
    await job_repo.update_celery_task_id(db, job_id=job_id, celery_task_id=async_result.id)
    log.info("generation_job_started", job_id=str(job_id), brand_id=str(brand_id))
    return GenerationJobCreatedResponse(job_id=job_id)


@router.get(
    "/{brand_id}/generate/{job_id}",
    response_model=GenerationJobStatusResponse,
)
async def get_generation_job(
    brand_id: uuid.UUID,
    job_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobStatusResponse:
    _ = current_user.id
    job = await job_repo.get_job(db, job_id=job_id, brand_id=brand_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return GenerationJobStatusResponse(
        id=job.id,
        status=job.status,  # type: ignore[arg-type]
        pipeline_stage=job.pipeline_stage,
        result=job.result_json,
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{brand_id}/generate/history",
    response_model=PaginatedResponse[GenerationHistoryItem],
)
async def list_generation_history(
    brand_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[GenerationHistoryItem]:
    _ = current_user.id
    rows, total = await job_repo.list_jobs_for_brand(db, brand_id=brand_id, page=page, page_size=page_size)
    items: list[GenerationHistoryItem] = []
    for row in rows:
        req = dict(row.request_json or {})
        summ = dict(row.summary_json or {})
        nvar = len((row.result_json or {}).get("variants") or []) if row.result_json else int(
            req.get("num_variants") or 3
        )
        chip_hook, chip_duration, chip_tone = _brief_chips_from_result(
            dict(row.result_json) if row.result_json else None
        )
        items.append(
            GenerationHistoryItem(
                id=row.id,
                campaign_description=str(req.get("campaign_description") or ""),
                num_variants=nvar,
                created_at=row.created_at,
                primary_summary=str(summ.get("primary_snippet") or ""),
                chip_hook=chip_hook,
                chip_duration=chip_duration,
                chip_tone=chip_tone,
            )
        )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{brand_id}/generate/{job_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def post_generation_feedback(
    brand_id: uuid.UUID,
    job_id: uuid.UUID,
    body: GenerationFeedbackBody,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _ = current_user.id
    job = await job_repo.get_job(db, job_id=job_id, brand_id=brand_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    norm = normalize_feedback_rating(body.rating)
    BRIEF_FEEDBACK_TOTAL.labels(rating=norm).inc()
    meta = {
        "generation_job_id": str(job_id),
        "variant_index": body.variant_index,
        "rating_raw": body.rating,
        "rating_normalized": norm,
        "feedback": body.feedback,
    }

    def _persist() -> None:
        with sync_session() as session:
            create_event(
                session,
                brand_id=brand_id,
                event_type=EventType.USER_NOTE.value,
                title="Generation feedback",
                event_date=datetime.now(timezone.utc),
                description=body.feedback[:4000] or None,
                impact_tags=["generation_feedback"],
                source=EventSource.USER_PROVIDED.value,
                metadata=meta,
            )

    await asyncio.to_thread(_persist)


@router.get(
    "/{brand_id}/generate/{job_id}/export",
)
async def export_generation_job(
    brand_id: uuid.UUID,
    job_id: uuid.UUID,
    format: str = Query("json", alias="format"),
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _ = current_user.id
    job = await job_repo.get_job(db, job_id=job_id, brand_id=brand_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.result_json:
        raise HTTPException(status_code=409, detail="Job not completed")
    fmt = format.lower()
    if fmt == "json":
        data = export_json(job.result_json)
        media = "application/json"
        fname = f"generation-{job_id}.json"
    elif fmt == "markdown":
        data = export_markdown(job.result_json)
        media = "text/markdown; charset=utf-8"
        fname = f"generation-{job_id}.md"
    elif fmt == "pdf":
        try:
            data = export_pdf(job.result_json)
        except RuntimeError as err:
            raise HTTPException(status_code=501, detail=str(err)) from err
        media = "application/pdf"
        fname = f"generation-{job_id}.pdf"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
