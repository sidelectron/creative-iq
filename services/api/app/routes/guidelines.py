"""Brand guidelines upload and retrieval (Phase 7 Step 2)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.dependencies import get_current_active_user, require_brand_role
from services.generation.guidelines_ingest import extract_text_from_upload, summarize_guidelines_text
from services.generation.schemas import StructuredGuidelinesBody
from shared.config.settings import settings
from shared.models.db import Brand, User
from shared.models.enums import BrandRole
from shared.utils.db import get_db
from shared.utils.gcs import generate_presigned_url, upload_file
from shared.utils.redis_client import cache_set

log = structlog.get_logger()

router = APIRouter(prefix="/brands", tags=["guidelines"])


def _safe_filename(name: str) -> str:
    base = name.split("/")[-1] or "guidelines"
    return re.sub(r"[^a-zA-Z0-9._-]", "_", base)[:200]


@router.post(
    "/{brand_id}/guidelines",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def upload_guidelines(
    brand_id: uuid.UUID,
    file: UploadFile = File(...),
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _ = current_user.id
    brand = await db.get(Brand, brand_id)
    if brand is None or brand.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Brand not found")
    content = await file.read()
    if len(content) > 25_000_000:
        raise HTTPException(status_code=413, detail="File too large")
    fname = _safe_filename(file.filename or "guidelines")
    dest = f"{brand_id}/guidelines/{fname}"
    ctype = file.content_type or "application/octet-stream"
    gcs_path = await upload_file(settings.storage_bucket_brand_assets, dest, content, ctype)
    content_hash = hashlib.sha256(content).hexdigest()
    merged_settings = dict(brand.settings or {})
    merged_settings["guidelines_content_sha256"] = content_hash
    brand.settings = merged_settings
    brand.guidelines_gcs_path = gcs_path
    await db.commit()

    text = await asyncio.to_thread(
        extract_text_from_upload,
        filename=fname,
        content=content,
    )
    summary = await asyncio.to_thread(
        summarize_guidelines_text,
        text=text,
        brand_name=brand.name,
    )
    cache_key = f"guidelines_summary:{brand_id}:{content_hash}"
    await cache_set(cache_key, json.dumps(summary), ttl_seconds=86400 * 30)
    log.info("guidelines_uploaded", brand_id=str(brand_id), path=gcs_path)


@router.post(
    "/{brand_id}/guidelines/structured",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def upload_structured_guidelines(
    brand_id: uuid.UUID,
    body: StructuredGuidelinesBody,
    _: object = Depends(require_brand_role(BrandRole.EDITOR)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _ = current_user.id
    brand = await db.get(Brand, brand_id)
    if brand is None or brand.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Brand not found")
    current = dict(brand.settings or {})
    current["guidelines"] = body.model_dump(exclude_none=True)
    brand.settings = current
    await db.commit()


@router.get("/{brand_id}/guidelines")
async def get_guidelines(
    brand_id: uuid.UUID,
    _: object = Depends(require_brand_role(BrandRole.VIEWER)),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    _ = current_user.id
    brand = await db.get(Brand, brand_id)
    if brand is None or brand.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Brand not found")
    structured = {}
    if isinstance(brand.settings, dict):
        g = brand.settings.get("guidelines")
        if isinstance(g, dict):
            structured = g
    signed: str | None = None
    raw_path = brand.guidelines_gcs_path
    if raw_path and "/" in raw_path:
        bucket, _, key = raw_path.partition("/")
        if bucket and key:
            signed = await generate_presigned_url(bucket, key, expiry_minutes=15)
    return {"structured": structured, "file_signed_url": signed}
