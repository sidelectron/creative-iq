"""Context assembly for generation pipeline (Phase 7 Step 3)."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.generation.context_models import GenerationContext
from services.generation.readers.brand_profile import load_brand_profile_payload
from shared.config.settings import settings
from shared.models.db import ABTest, Ad, AdPerformance, Brand, BrandEra, UserBrandPreference
from shared.utils.redis_client import cache_get

log = structlog.get_logger()

_PRIMARY_PLATFORM_WINDOW_DAYS = 90


def _profile_top_attributes(profile_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort extraction of top-scoring attributes from profile JSON."""
    out: list[dict[str, Any]] = []
    attrs = profile_data.get("attributes") or profile_data.get("creative_attributes")
    if isinstance(attrs, dict):
        for name, payload in list(attrs.items())[:40]:
            if not isinstance(payload, dict):
                continue
            score = payload.get("score") or payload.get("mean_score") or payload.get("lift")
            n = payload.get("n") or payload.get("sample_size") or payload.get("ads_count")
            conf = payload.get("confidence") or payload.get("confidence_level")
            out.append(
                {
                    "name": str(name),
                    "score": score,
                    "sample_size": n,
                    "confidence": conf,
                    "raw": payload,
                }
            )
    return out[:30]


def _audience_signals(profile_data: dict[str, Any], target_audience: str | None) -> dict[str, Any]:
    aud = profile_data.get("audience") or profile_data.get("audience_signals")
    if isinstance(aud, dict):
        base = dict(aud)
    else:
        base = {"notes": str(aud) if aud else ""}
    if target_audience:
        base["user_target_audience"] = target_audience
    return base


def _timeline_last_sync(brand_id: uuid.UUID, n: int) -> list[dict[str, Any]]:
    """Last N merged timeline rows (same merge rules as services.chat.timeline_service)."""
    from shared.utils.db_sync import SessionLocal

    from services.chat.timeline_service import list_timeline_items

    with SessionLocal() as session:
        items, _ = list_timeline_items(
            session,
            brand_id=brand_id,
            event_type=None,
            source=None,
            start_date=None,
            end_date=None,
            page=1,
            page_size=max(n, 1),
        )
    out: list[dict[str, Any]] = []
    for i in items[:n]:
        ts = i["timestamp"]
        at = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        out.append(
            {
                "event_type": i["event_type"],
                "title": i["title"],
                "source": i.get("source", ""),
                "at": at,
            }
        )
    return out


async def _active_era(db: AsyncSession, *, brand_id: uuid.UUID) -> dict[str, Any] | None:
    row = await db.scalar(
        select(BrandEra)
        .where(BrandEra.brand_id == brand_id, BrandEra.end_date.is_(None))
        .order_by(BrandEra.start_date.desc())
    )
    if row is None:
        return None
    return {
        "era_id": str(row.id),
        "era_name": row.era_name,
        "start_date": row.start_date.isoformat(),
        "triggering_event_id": str(row.triggering_event_id or ""),
    }


async def _top_ads_postgres(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    platform: str,
    limit: int,
) -> list[dict[str, Any]]:
    ctr_expr = (
        func.sum(AdPerformance.clicks) / func.nullif(func.sum(AdPerformance.impressions), 0)
    ).label("ctr")
    stmt = (
        select(Ad.id, Ad.title, Ad.platform, ctr_expr)
        .join(AdPerformance, AdPerformance.ad_id == Ad.id)
        .where(Ad.brand_id == brand_id, Ad.deleted_at.is_(None), Ad.platform == platform)
        .group_by(Ad.id, Ad.title, Ad.platform)
        .order_by(func.sum(AdPerformance.impressions).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "ad_id": str(r[0]),
            "title": r[1],
            "platform": r[2],
            "ctr": float(r[3]) if r[3] is not None else None,
        }
        for r in rows
    ]


def _try_snowflake_top_ads(brand_id: uuid.UUID, platform: str, limit: int) -> list[dict[str, Any]]:
    if not settings.snowflake_account:
        return []
    try:
        from services.profile_engine.storage.repositories import snowflake_query

        q = f"""
        SELECT ad_id, title, platform, ctr
        FROM marts.ad_summary
        WHERE brand_id = '{brand_id!s}' AND platform = '{platform}'
        ORDER BY ctr DESC NULLS LAST
        LIMIT {limit}
        """
        return snowflake_query(q, query_type="ad_summary")[:limit]
    except Exception:
        return []


async def resolve_primary_platform(db: AsyncSession, *, brand_id: uuid.UUID) -> str:
    """Prefer settings override, then platform with most ads in last N days, then all-time."""
    brand = await db.get(Brand, brand_id)
    if brand and isinstance(brand.settings, dict):
        p = brand.settings.get("primary_platform")
        if isinstance(p, str) and p.strip():
            return p.strip().lower()

    cutoff = datetime.now(timezone.utc) - timedelta(days=_PRIMARY_PLATFORM_WINDOW_DAYS)

    async def _top_platform(since: datetime | None) -> str | None:
        stmt = (
            select(Ad.platform, func.count().label("c"))
            .where(Ad.brand_id == brand_id, Ad.deleted_at.is_(None))
            .group_by(Ad.platform)
            .order_by(func.count().desc())
            .limit(1)
        )
        if since is not None:
            stmt = stmt.where(Ad.created_at >= since)
        row = await db.execute(stmt)
        first = row.first()
        return str(first[0]) if first else None

    plat = await _top_platform(cutoff)
    if plat:
        return plat
    plat = await _top_platform(None)
    return plat or "meta"


async def assemble_generation_context(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    user_id: uuid.UUID,
    platform: str | None,
    campaign_description: str,
    target_audience: str | None,
    user_adjustments: str | None = None,
) -> GenerationContext:
    """Build structured context for brief generation (Pydantic envelope)."""
    t0 = time.perf_counter()
    plat = platform or await resolve_primary_platform(db, brand_id=brand_id)
    brand = await db.get(Brand, brand_id)

    profile_task = load_brand_profile_payload(db, brand_id=brand_id, platform=plat)
    era_task = _active_era(db, brand_id=brand_id)
    timeline_task = asyncio.to_thread(_timeline_last_sync, brand_id, 5)
    pref_task = db.scalar(
        select(UserBrandPreference).where(
            UserBrandPreference.brand_id == brand_id,
            UserBrandPreference.user_id == user_id,
        )
    )
    ads_pg_task = _top_ads_postgres(db, brand_id=brand_id, platform=plat, limit=5)

    profile_data, current_era, timeline_items, pref, ads_rows = await asyncio.gather(
        profile_task,
        era_task,
        timeline_task,
        pref_task,
        ads_pg_task,
    )
    ab_rows = list(
        (
            await db.scalars(
                select(ABTest).where(
                    ABTest.brand_id == brand_id,
                    ABTest.status.in_(["proposed", "active"]),
                )
            )
        ).all()
    )

    snowflake_ads = await asyncio.to_thread(_try_snowflake_top_ads, brand_id, plat, 5)
    reference_ads = snowflake_ads if snowflake_ads else ads_rows

    guidelines_structured: dict[str, Any] = {}
    if brand and isinstance(brand.settings, dict):
        g = brand.settings.get("guidelines")
        if isinstance(g, dict):
            guidelines_structured = g

    doc_summary: dict[str, Any] = {"summary": "", "key_rules": []}
    if brand and isinstance(brand.settings, dict):
        content_hash = brand.settings.get("guidelines_content_sha256")
        if isinstance(content_hash, str) and content_hash.strip():
            raw = await cache_get(f"guidelines_summary:{brand_id}:{content_hash.strip()}")
            if raw:
                try:
                    doc_summary = json.loads(raw)
                except json.JSONDecodeError:
                    doc_summary = {"summary": raw, "key_rules": []}
        elif brand.guidelines_gcs_path:
            raw = await cache_get(f"guidelines_summary:{brand_id}:{brand.guidelines_gcs_path}")
            if raw:
                try:
                    doc_summary = json.loads(raw)
                except json.JSONDecodeError:
                    doc_summary = {"summary": raw, "key_rules": []}

    profile_payload = profile_data or {}
    assembly_ms = int((time.perf_counter() - t0) * 1000)
    if assembly_ms > 2000:
        log.warning("context_assembly_slow", brand_id=str(brand_id), ms=assembly_ms)

    return GenerationContext(
        brand_id=str(brand_id),
        brand_name=brand.name if brand else "",
        industry=brand.industry if brand else None,
        platform=plat,
        campaign_description=campaign_description,
        profile_raw=profile_payload,
        profile_top_attributes=_profile_top_attributes(profile_payload),
        audience_signals=_audience_signals(profile_payload, target_audience),
        current_era=current_era,
        timeline_last_5=timeline_items,
        user_preferences=(
            {
                "creative_preferences": pref.creative_preferences,
                "strategic_notes": pref.strategic_notes,
                "success_metrics": pref.success_metrics,
            }
            if pref
            else None
        ),
        guidelines_structured=guidelines_structured,
        guidelines_document_summary=doc_summary,
        reference_ads=reference_ads,
        active_ab_tests=[
            {
                "id": str(t.id),
                "status": t.status,
                "attribute_tested": t.attribute_tested,
                "hypothesis": t.hypothesis,
            }
            for t in ab_rows
        ],
        assembly_ms=assembly_ms,
        user_adjustments=user_adjustments,
    )
