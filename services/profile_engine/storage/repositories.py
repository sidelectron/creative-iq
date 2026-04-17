"""Data access repositories for profile engine."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from shared.config.settings import settings
from shared.models.db import ABTest, Ad, Brand, BrandEra, BrandEvent, BrandProfile, IndustryPreset
from shared.utils.gemini import embed_text
from services.profile_engine import metrics


def snowflake_query(
    query: str,
    params: tuple[Any, ...] = (),
    *,
    query_type: str = "generic",
) -> list[dict[str, Any]]:
    """Execute Snowflake query and return dict rows."""
    import snowflake.connector

    conn = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        role=settings.snowflake_role,
    )
    try:
        with metrics.SNOWFLAKE_QUERY_DURATION_SECONDS.labels(query_type=query_type).time():
            with conn.cursor() as cur:
                cur.execute(query, params)
                cols = [col[0].lower() for col in cur.description or []]
                return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_brand(session: Session, brand_id: uuid.UUID) -> Brand | None:
    return session.get(Brand, brand_id)


def get_brand_eras(session: Session, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(BrandEra).where(BrandEra.brand_id == brand_id).order_by(BrandEra.start_date.asc())
    ).all()
    return [{"start_date": r.start_date, "end_date": r.end_date, "era_name": r.era_name} for r in rows]


def get_latest_profile(
    session: Session, brand_id: uuid.UUID, platform: str, audience_segment: str = "all"
) -> BrandProfile | None:
    return session.scalar(
        select(BrandProfile).where(
            BrandProfile.brand_id == brand_id,
            BrandProfile.platform == platform,
            BrandProfile.audience_segment == audience_segment,
        )
    )


def upsert_profile(
    session: Session,
    *,
    brand_id: uuid.UUID,
    platform: str,
    profile_data: dict[str, Any],
    overall_confidence: float,
    total_ads_analyzed: int,
    model_gcs_path: str,
    scoring_stage: str,
) -> BrandProfile:
    row = get_latest_profile(session, brand_id, platform)
    now = datetime.now(timezone.utc)
    if row is None:
        row = BrandProfile(
            brand_id=brand_id,
            platform=platform,
            audience_segment="all",
            scoring_stage=scoring_stage,
            profile_data=profile_data,
            overall_confidence=Decimal(str(round(overall_confidence, 4))),
            total_ads_analyzed=total_ads_analyzed,
            model_gcs_path=model_gcs_path,
            computed_at=now,
        )
        session.add(row)
    else:
        row.scoring_stage = scoring_stage
        row.profile_data = profile_data
        row.overall_confidence = Decimal(str(round(overall_confidence, 4)))
        row.total_ads_analyzed = total_ads_analyzed
        row.model_gcs_path = model_gcs_path
        row.computed_at = now
    session.commit()
    return row


def get_industry_preset(
    session: Session,
    *,
    industry: str | None,
    platform: str,
    audience_segment: str = "all",
) -> dict[str, Any]:
    selected = None
    if industry:
        selected = session.scalar(
            select(IndustryPreset).where(
                and_(
                    IndustryPreset.industry == industry,
                    IndustryPreset.platform == platform,
                    IndustryPreset.audience_segment == audience_segment,
                )
            )
        )
    if selected is None:
        selected = session.scalar(
            select(IndustryPreset).where(
                and_(
                    IndustryPreset.industry == "all_industries",
                    IndustryPreset.platform == platform,
                    IndustryPreset.audience_segment == audience_segment,
                )
            )
        )
    return dict(selected.baseline_profile) if selected else {"categorical": {}}


def insert_brand_event(
    session: Session,
    *,
    brand_id: uuid.UUID,
    event_type: str,
    title: str,
    description: str,
    source: str,
    metadata: dict[str, Any],
    event_date: datetime | None = None,
    impact_tags: list[str] | None = None,
) -> BrandEvent:
    tags = impact_tags or []
    text = " | ".join([title, description or "", ", ".join(tags)]).strip(" |")
    embedding = embed_text(text=text) if text else None
    row = BrandEvent(
        brand_id=brand_id,
        event_type=event_type,
        title=title,
        description=description,
        source=source,
        event_date=event_date or datetime.now(timezone.utc),
        impact_tags=tags,
        event_metadata=metadata,
        embedding=embedding,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def drift_alert_exists(
    session: Session,
    *,
    brand_id: uuid.UUID,
    attribute_key: str,
    min_event_date: datetime,
) -> bool:
    rows = session.scalars(
        select(BrandEvent).where(
            BrandEvent.brand_id == brand_id,
            BrandEvent.event_type == "performance_anomaly",
            BrandEvent.source == "auto_detected",
            BrandEvent.event_date >= min_event_date,
        )
    ).all()
    for row in rows:
        if str((row.event_metadata or {}).get("attribute_key", "")) == attribute_key:
            return True
    return False


def create_ab_test(session: Session, row: ABTest) -> ABTest:
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str, separators=(",", ":"), sort_keys=True)


def count_ads_for_brand(session: Session, brand_id: uuid.UUID, platform: str) -> int:
    stmt = select(Ad).where(Ad.brand_id == brand_id, Ad.platform == platform, Ad.deleted_at.is_(None))
    return len(list(session.scalars(stmt).all()))


def get_mart_freshness() -> list[dict[str, Any]]:
    """Return latest mart freshness by brand/platform from Snowflake."""
    try:
        return snowflake_query(
            """
            SELECT brand_id, platform, MAX(computed_at) AS mart_computed_at
            FROM MARTS.MART_BRAND_OVERVIEW
            GROUP BY brand_id, platform
            """,
            query_type="mart_freshness",
        )
    except Exception:
        return []


def list_changed_brand_platforms(session: Session) -> list[tuple[uuid.UUID, str]]:
    """Compare mart freshness vs profile freshness and return changed tuples."""
    changed: list[tuple[uuid.UUID, str]] = []
    for row in get_mart_freshness():
        try:
            brand_id = uuid.UUID(str(row.get("brand_id")))
        except (TypeError, ValueError):
            continue
        platform = str(row.get("platform") or "")
        if not platform:
            continue
        mart_ts = row.get("mart_computed_at")
        latest = get_latest_profile(session, brand_id, platform)
        if latest is None:
            changed.append((brand_id, platform))
            continue
        if mart_ts is None or mart_ts > latest.computed_at:
            changed.append((brand_id, platform))
    return changed


def get_temporal_rows(brand_id: uuid.UUID, platform: str, metric: str) -> list[dict[str, Any]]:
    """Fetch per-ad rows from int table for temporal weighted scoring."""
    metric_col = {
        "ctr": "ctr",
        "cpa": "cpa",
        "roas": "roas",
    }.get(metric, "ctr")
    query = f"""
        SELECT
            ad_id,
            published_at,
            hook_type,
            narrative_arc,
            emotional_tone,
            cta_type,
            visual_style,
            {metric_col} AS metric_value
        FROM INTERMEDIATE.INT_ADS_WITH_FINGERPRINTS
        WHERE brand_id = %s
          AND platform = %s
          AND {metric_col} IS NOT NULL
    """
    try:
        return snowflake_query(
            query,
            (str(brand_id), platform),
            query_type="temporal_rows",
        )
    except Exception:
        return []


def get_brand_data_span_days(brand_id: uuid.UUID, platform: str) -> int:
    """Return number of days covered by per-ad data in Snowflake."""
    try:
        rows = snowflake_query(
            """
            SELECT DATEDIFF('day', MIN(published_at), MAX(published_at)) AS span_days
            FROM INTERMEDIATE.INT_ADS_WITH_FINGERPRINTS
            WHERE brand_id = %s AND platform = %s
            """,
            (str(brand_id), platform),
            query_type="data_span_days",
        )
    except Exception:
        return 0
    if not rows:
        return 0
    return int(rows[0].get("span_days") or 0)
