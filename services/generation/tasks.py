"""Celery tasks for generation pipeline."""

from __future__ import annotations

import asyncio
import uuid

from celery import Task

from shared.celery_app import celery_app


@celery_app.task(bind=True, name="services.generation.tasks.generation_tasks.run_generation_job")
def run_generation_job(self: Task, job_id: str) -> dict[str, str]:
    """Run async generation pipeline for persisted job."""
    from services.generation.pipeline import run_generation_pipeline

    jid = uuid.UUID(job_id)
    asyncio.run(run_generation_pipeline(jid))
    return {"status": "ok", "job_id": job_id}
