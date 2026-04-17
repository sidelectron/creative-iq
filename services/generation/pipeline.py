"""End-to-end generation pipeline (Phase 7 Steps 3–7) — delegates to LangGraph."""

from __future__ import annotations

import uuid

import structlog

from services.generation.graph import invoke_generation_graph
from services.generation.redis_notify import publish_generation_update_sync
from services.generation.repositories import jobs as job_repo
from shared.utils.db import AsyncSessionLocal

log = structlog.get_logger()


async def run_generation_pipeline(job_id: uuid.UUID) -> None:
    """Execute full generation for a persisted job row."""
    try:
        await invoke_generation_graph(job_id)
    except Exception as err:
        log.exception("generation_pipeline_failed", job_id=str(job_id))
        async with AsyncSessionLocal() as db:
            await job_repo.fail_job(db, job_id=job_id, message=str(err))
        publish_generation_update_sync(
            job_id,
            {"type": "error", "message": str(err)[:500], "stage": "failed"},
        )
