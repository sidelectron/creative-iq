"""Ad routes under a brand."""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from datetime import date, datetime, time, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid_utils.compat import uuid7

from shared.celery_app import celery_app
from shared.config.settings import settings
from shared.models.db import Ad, AdPerformance, BrandMember
from shared.models.enums import AdSource, AdStatus, BrandRole, Platform
from shared.models.schemas import (
    AdCompareResponse,
    AdDetailResponse,
    AdPerformanceSummary,
    AdResponse,
    BatchDecomposeBody,
    BatchDecomposeResponse,
    CreativeFingerprintResponse,
    PaginatedResponse,
    ad_performance_response_from_model,
    ad_response_from_model,
)
from shared.utils import gcs
from shared.utils.db import get_db
from services.api.app.dependencies import require_brand_role

router = APIRouter(tags=["ads"])

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


async def _ffprobe_video(path: Path) -> tuple[float | None, str | None]:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        return None, None
    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError:
        return None, None
    duration: float | None = None
    if "format" in data and data["format"].get("duration") is not None:
        try:
            duration = float(data["format"]["duration"])
        except (TypeError, ValueError):
            duration = None
    width = height = None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            if duration is None and stream.get("duration") is not None:
                try:
                    duration = float(stream["duration"])
                except (TypeError, ValueError):
                    pass
            break
    resolution = f"{int(width)}x{int(height)}" if width and height else None
    return duration, resolution


@router.post("/upload", response_model=AdResponse, status_code=status.HTTP_201_CREATED)
async def upload_ad(
    brand_id: uuid.UUID,
    video: UploadFile = File(...),
    platform: str = Form(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    published_at: str | None = Form(None),
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> AdResponse:
    try:
        plat = Platform(platform.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid platform",
        )
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type; allowed: {', '.join(sorted(VIDEO_EXTENSIONS))}",
        )
    pub_dt: datetime | None = None
    if published_at:
        try:
            raw = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            pub_dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="published_at must be ISO-8601 datetime",
            )

    ad_id = uuid7()
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            total = 0
            while True:
                chunk = await video.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Video exceeds 500MB limit",
                    )
                tmp.write(chunk)
        duration_seconds, resolution = await _ffprobe_video(tmp_path)
        data = tmp_path.read_bytes()
        key = f"{brand_id}/{ad_id}/original{suffix}"
        bucket = settings.storage_bucket_raw_ads
        gcs_path = await gcs.upload_file(
            bucket,
            key,
            data,
            video.content_type or "application/octet-stream",
        )
        ad = Ad(
            id=ad_id,
            brand_id=brand_id,
            platform=plat.value,
            title=title,
            description=description,
            source=AdSource.UPLOAD.value,
            status=AdStatus.INGESTED.value,
            published_at=pub_dt,
            gcs_video_path=gcs_path,
            duration_seconds=duration_seconds,
            resolution=resolution,
        )
        db.add(ad)
        await db.commit()
        celery_app.send_task(
            "services.decomposition.tasks.decompose_ad",
            args=[str(ad_id)],
            queue="decomposition",
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    await db.refresh(ad)
    if ad.gcs_video_path:
        bkt, _, obj_key = ad.gcs_video_path.partition("/")
        signed = await gcs.generate_presigned_url(bkt, obj_key, expiry_minutes=60)
    else:
        signed = None
    return ad_response_from_model(ad, signed_video_url=signed)


@router.get("", response_model=PaginatedResponse[AdResponse])
async def list_ads(
    brand_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
    platform: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    published_from: date | None = Query(None),
    published_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_fingerprint: bool = Query(False, description="Include fingerprint attributes for client-side search"),
) -> PaginatedResponse[AdResponse]:
    agg = (
        select(
            AdPerformance.ad_id.label("ad_id"),
            func.coalesce(func.sum(AdPerformance.impressions), 0).label("ti"),
            func.coalesce(func.sum(AdPerformance.clicks), 0).label("tc"),
        )
        .group_by(AdPerformance.ad_id)
        .subquery()
    )
    filters = [Ad.brand_id == brand_id, Ad.deleted_at.is_(None)]
    if platform:
        try:
            filters.append(Ad.platform == Platform(platform.lower()).value)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid platform filter")
    if status_filter:
        filters.append(Ad.status == status_filter)
    if published_from is not None:
        start = datetime.combine(published_from, time.min, tzinfo=timezone.utc)
        filters.append(Ad.published_at.is_not(None))
        filters.append(Ad.published_at >= start)
    if published_to is not None:
        end = datetime.combine(published_to, time.max, tzinfo=timezone.utc)
        filters.append(Ad.published_at.is_not(None))
        filters.append(Ad.published_at <= end)

    total_count = int(await db.scalar(select(func.count()).select_from(Ad).where(*filters)) or 0)
    offset = (page - 1) * page_size
    stmt = (
        select(Ad, agg.c.ti, agg.c.tc)
        .outerjoin(agg, agg.c.ad_id == Ad.id)
        .where(*filters)
        .order_by(Ad.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if include_fingerprint:
        stmt = stmt.options(selectinload(Ad.fingerprint))
    result = await db.execute(stmt)
    rows = result.all()
    items: list[AdResponse] = []
    for row_ad, ti_raw, tc_raw in rows:
        ti = int(ti_raw or 0)
        tc = int(tc_raw or 0)
        avg_ctr = (tc / ti) if ti > 0 else None
        summary = AdPerformanceSummary(
            total_impressions=ti,
            total_clicks=tc,
            average_ctr=avg_ctr,
        )
        signed = None
        if row_ad.gcs_video_path:
            bkt, _, obj_key = row_ad.gcs_video_path.partition("/")
            signed = await gcs.generate_presigned_url(bkt, obj_key, expiry_minutes=60)
        fp_attrs: dict | None = None
        if include_fingerprint:
            fp = getattr(row_ad, "fingerprint", None)
            raw_attrs = getattr(fp, "attributes", None) if fp is not None else None
            fp_attrs = dict(raw_attrs) if isinstance(raw_attrs, dict) else None
        items.append(
            ad_response_from_model(
                row_ad,
                signed_video_url=signed,
                performance_summary=summary,
                fingerprint_attributes=fp_attrs,
            )
        )
    return PaginatedResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.get("/compare", response_model=AdCompareResponse)
async def compare_ads(
    brand_id: uuid.UUID,
    ad_ids: str = Query(..., description="Comma-separated ad UUIDs (2–5)"),
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> AdCompareResponse:
    raw = [a.strip() for a in ad_ids.split(",") if a.strip()]
    if len(raw) < 2 or len(raw) > 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide between 2 and 5 ad_ids",
        )
    try:
        ids = [uuid.UUID(x) for x in raw]
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid ad UUID")

    result = await db.execute(
        select(Ad)
        .options(selectinload(Ad.fingerprint))
        .where(
            Ad.brand_id == brand_id,
            Ad.id.in_(ids),
            Ad.deleted_at.is_(None),
        )
    )
    ads = list(result.scalars().all())
    if len(ads) != len(ids):
        raise HTTPException(status_code=404, detail="One or more ads not found")

    payloads: list[dict] = []
    attr_maps: list[dict] = []
    for a in sorted(ads, key=lambda x: ids.index(x.id)):
        fp = a.fingerprint
        attrs = (fp.attributes if fp else {}) or {}
        attr_maps.append(attrs)
        payloads.append(
            {
                "ad_id": str(a.id),
                "status": a.status,
                "attributes": attrs,
            }
        )

    keys: set[str] = set()
    for m in attr_maps:
        keys.update(m.keys())
    differences: dict[str, list] = {}
    for k in sorted(keys):
        vals = [m.get(k) for m in attr_maps]

        def _norm(v: object) -> str:
            if isinstance(v, (dict, list)):
                return json.dumps(v, sort_keys=True, default=str)
            return str(v)

        if len({_norm(v) for v in vals}) > 1:
            differences[k] = vals

    return AdCompareResponse(ads=payloads, differences=differences)


@router.post("/decompose-batch", response_model=BatchDecomposeResponse)
async def decompose_batch(
    brand_id: uuid.UUID,
    body: BatchDecomposeBody,
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> BatchDecomposeResponse:
    queued: list[uuid.UUID] = []
    if body.ad_ids == "all":
        result = await db.execute(
            select(Ad.id).where(
                Ad.brand_id == brand_id,
                Ad.deleted_at.is_(None),
                Ad.status.in_([AdStatus.INGESTED.value, AdStatus.FAILED.value]),
            )
        )
        candidates = [row[0] for row in result.all()]
    else:
        uuids = list(dict.fromkeys(body.ad_ids))
        result = await db.execute(
            select(Ad.id).where(
                Ad.brand_id == brand_id,
                Ad.id.in_(uuids),
                Ad.deleted_at.is_(None),
                Ad.status.in_([AdStatus.INGESTED.value, AdStatus.FAILED.value]),
            )
        )
        found = {row[0] for row in result.all()}
        candidates = [i for i in uuids if i in found]

    for aid in candidates:
        celery_app.send_task(
            "services.decomposition.tasks.decompose_ad",
            args=[str(aid)],
            queue="decomposition",
        )
        queued.append(aid)

    return BatchDecomposeResponse(queued_count=len(queued), ad_ids=queued)


@router.get("/{ad_id}", response_model=AdDetailResponse)
async def get_ad(
    brand_id: uuid.UUID,
    ad_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> AdDetailResponse:
    result = await db.execute(
        select(Ad)
        .options(
            selectinload(Ad.performance_rows),
            selectinload(Ad.fingerprint),
        )
        .where(
            Ad.id == ad_id,
            Ad.brand_id == brand_id,
            Ad.deleted_at.is_(None),
        )
    )
    ad = result.scalar_one_or_none()
    if ad is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
    ad.performance_rows = sorted(ad.performance_rows, key=lambda p: p.date)
    perfs = [ad_performance_response_from_model(p) for p in ad.performance_rows]
    fp = ad.fingerprint
    if fp and ad.status == AdStatus.DECOMPOSED.value:
        fp_out = CreativeFingerprintResponse(
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
    else:
        fp_out = None
    signed = None
    if ad.gcs_video_path:
        bkt, _, obj_key = ad.gcs_video_path.partition("/")
        signed = await gcs.generate_presigned_url(bkt, obj_key, expiry_minutes=60)
    base = ad_response_from_model(ad, signed_video_url=signed)
    return AdDetailResponse.model_validate(
        {
            **base.model_dump(),
            "performances": perfs,
            "fingerprint": fp_out,
        }
    )


@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad(
    brand_id: uuid.UUID,
    ad_id: uuid.UUID,
    _: BrandMember = Depends(require_brand_role(BrandRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Ad).where(
            Ad.id == ad_id,
            Ad.brand_id == brand_id,
            Ad.deleted_at.is_(None),
        )
    )
    ad = result.scalar_one_or_none()
    if ad is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
    ad.deleted_at = datetime.now(timezone.utc)
    await db.commit()
