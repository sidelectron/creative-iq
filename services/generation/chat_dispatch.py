"""Synchronous helpers to enqueue generation from the chat agent (sync tool context)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from uuid_utils.compat import uuid7

from services.generation.tasks import run_generation_job
from shared.models.db import GenerationJob
from shared.utils.db_sync import SessionLocal


def _is_vague_campaign(message: str) -> bool:
    text = message.strip().lower()
    if re.search(r"variant\s*\d+", text, flags=re.IGNORECASE):
        return False
    if "job" in text and re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text, flags=re.IGNORECASE):
        return False
    if len(text) < 25:
        return True
    hints = ("brief", "campaign", "creative", "ad ", "ads ", "video", "launch")
    return not any(h in text for h in hints)


def maybe_clarify_campaign(message: str) -> str | None:
    """Return clarifying question if campaign intent is too vague."""
    if _is_vague_campaign(message):
        return (
            "What product or service is this campaign for? Any specific goals — brand awareness, "
            "conversions, app installs?"
        )
    return None


def enqueue_generation_job(
    *,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    campaign_description: str,
    platform: str | None = None,
    num_variants: int = 3,
    include_scene_breakdown: bool = True,
    parent_job_id: uuid.UUID | None = None,
    variant_index: int | None = None,
    user_adjustments: str | None = None,
    target_audience: str | None = None,
) -> uuid.UUID:
    """Insert job row and dispatch Celery task."""
    job_id = uuid7()
    desc = campaign_description
    with SessionLocal() as session:
        if parent_job_id is not None:
            pj = session.get(GenerationJob, parent_job_id)
            if pj is not None and pj.brand_id == brand_id:
                prev = dict(pj.request_json or {})
                desc = str(prev.get("campaign_description") or desc)
                if platform is None and prev.get("platform"):
                    platform = str(prev.get("platform"))
                if target_audience is None and prev.get("target_audience"):
                    target_audience = str(prev.get("target_audience"))
        request_json: dict[str, Any] = {
            "campaign_description": desc,
            "platform": platform,
            "target_audience": target_audience,
            "num_variants": num_variants,
            "include_scene_breakdown": include_scene_breakdown,
        }
        if parent_job_id is not None:
            request_json["parent_job_id"] = str(parent_job_id)
        if variant_index is not None:
            request_json["variant_index"] = variant_index
        if user_adjustments:
            request_json["user_adjustments"] = user_adjustments
        row = GenerationJob(
            id=job_id,
            brand_id=brand_id,
            created_by_user_id=user_id,
            status="processing",
            pipeline_stage="queued",
            request_json=request_json,
            started_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
    async_result = run_generation_job.delay(str(job_id))
    with SessionLocal() as session:
        gj = session.get(GenerationJob, job_id)
        if gj is not None:
            gj.celery_task_id = async_result.id
            session.commit()
    return job_id
