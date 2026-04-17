"""Persistence for generation jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.db import GenerationJob


async def get_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> GenerationJob | None:
    return await db.scalar(
        select(GenerationJob).where(
            GenerationJob.id == job_id,
            GenerationJob.brand_id == brand_id,
        )
    )


async def create_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    request_json: dict[str, Any],
    celery_task_id: str | None,
) -> GenerationJob:
    row = GenerationJob(
        id=job_id,
        brand_id=brand_id,
        created_by_user_id=user_id,
        status="processing",
        pipeline_stage="queued",
        request_json=request_json,
        celery_task_id=celery_task_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_job_stage(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    stage: str | None,
) -> None:
    await db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id)
        .values(pipeline_stage=stage)
    )
    await db.commit()


async def complete_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    result_json: dict[str, Any],
    summary_json: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id)
        .values(
            status="completed",
            pipeline_stage="completed",
            result_json=result_json,
            summary_json=summary_json,
            completed_at=now,
            error=None,
        )
    )
    await db.commit()


async def update_celery_task_id(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    celery_task_id: str,
) -> None:
    await db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id)
        .values(celery_task_id=celery_task_id)
    )
    await db.commit()


async def fail_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    message: str,
) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id)
        .values(
            status="failed",
            pipeline_stage="failed",
            error=message[:4000],
            completed_at=now,
        )
    )
    await db.commit()


async def list_jobs_for_brand(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[GenerationJob], int]:
    from sqlalchemy import func

    total = await db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.brand_id == brand_id)
    )
    total = int(total or 0)
    offset = (page - 1) * page_size
    rows = list(
        (
            await db.scalars(
                select(GenerationJob)
                .where(GenerationJob.brand_id == brand_id)
                .order_by(GenerationJob.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
        ).all()
    )
    return rows, total
