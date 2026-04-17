"""Performance-oriented chat tools."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select

from services.chat.schemas import CompareAdsInput, QueryAdPerformanceInput
from services.chat.tools.common import tool
from shared.models.db import Ad, AdPerformance, CreativeFingerprint
from shared.utils.db_sync import sync_session


def _metric(row: AdPerformance) -> dict[str, float | None]:
    return {"ctr": row.ctr, "cpa": row.cpa, "roas": row.roas}


@tool
def query_ad_performance(payload: QueryAdPerformanceInput) -> dict[str, Any]:
    """Return aggregate performance for brand/date/platform filters."""
    with sync_session() as session:
        ad_stmt = select(Ad.id).where(Ad.brand_id == payload.brand_id, Ad.deleted_at.is_(None))
        if payload.platform:
            ad_stmt = ad_stmt.where(Ad.platform == payload.platform)
        ad_ids = [row for row in session.scalars(ad_stmt).all()]
        if not ad_ids:
            return {"total_ads": 0, "rows": 0}
        stmt = select(AdPerformance).where(AdPerformance.ad_id.in_(ad_ids))
        if payload.date_range_start:
            stmt = stmt.where(AdPerformance.date >= payload.date_range_start.date())
        if payload.date_range_end:
            stmt = stmt.where(AdPerformance.date <= payload.date_range_end.date())
        rows = list(session.scalars(stmt).all())
        if not rows:
            return {"total_ads": len(ad_ids), "rows": 0}
        ctrs = [r.ctr for r in rows if r.ctr is not None]
        cpas = [r.cpa for r in rows if r.cpa is not None]
        roases = [r.roas for r in rows if r.roas is not None]
        return {
            "total_ads": len(ad_ids),
            "rows": len(rows),
            "average_ctr": float(sum(ctrs) / len(ctrs)) if ctrs else None,
            "average_cpa": float(sum(cpas) / len(cpas)) if cpas else None,
            "average_roas": float(sum(roases) / len(roases)) if roases else None,
        }


@tool
def compare_ads(payload: CompareAdsInput) -> dict[str, Any]:
    """Compare two ads by fingerprints and observed performance."""
    with sync_session() as session:
        ad1 = session.get(Ad, payload.ad_id_1)
        ad2 = session.get(Ad, payload.ad_id_2)
        if ad1 is None or ad2 is None:
            return {"status": "missing_ads"}
        fp1 = session.scalar(select(CreativeFingerprint).where(CreativeFingerprint.ad_id == ad1.id))
        fp2 = session.scalar(select(CreativeFingerprint).where(CreativeFingerprint.ad_id == ad2.id))
        perf1 = list(session.scalars(select(AdPerformance).where(AdPerformance.ad_id == ad1.id)).all())
        perf2 = list(session.scalars(select(AdPerformance).where(AdPerformance.ad_id == ad2.id)).all())
        diffs: dict[str, Any] = {}
        attrs1 = dict((fp1.attributes if fp1 else {}) or {})
        attrs2 = dict((fp2.attributes if fp2 else {}) or {})
        for key in sorted(set(attrs1.keys()) | set(attrs2.keys())):
            if attrs1.get(key) != attrs2.get(key):
                diffs[key] = {"ad_1": attrs1.get(key), "ad_2": attrs2.get(key)}
        avg1 = {
            "ctr": float(sum(v.ctr for v in perf1 if v.ctr is not None) / max(len([v for v in perf1 if v.ctr is not None]), 1)),
            "roas": float(sum(v.roas for v in perf1 if v.roas is not None) / max(len([v for v in perf1 if v.roas is not None]), 1)),
        }
        avg2 = {
            "ctr": float(sum(v.ctr for v in perf2 if v.ctr is not None) / max(len([v for v in perf2 if v.ctr is not None]), 1)),
            "roas": float(sum(v.roas for v in perf2 if v.roas is not None) / max(len([v for v in perf2 if v.roas is not None]), 1)),
        }
        return {
            "ad_1": {"id": str(ad1.id), "platform": ad1.platform, "metrics": avg1},
            "ad_2": {"id": str(ad2.id), "platform": ad2.platform, "metrics": avg2},
            "attribute_differences": diffs,
        }


@tool
def get_drift_alerts(brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return auto-detected drift/performance anomaly events for a brand."""
    from shared.models.db import BrandEvent

    with sync_session() as session:
        rows = list(
            session.scalars(
                select(BrandEvent).where(
                    BrandEvent.brand_id == brand_id,
                    BrandEvent.event_type == "performance_anomaly",
                )
            ).all()
        )
        return [
            {
                "event_id": str(r.id),
                "event_date": r.event_date.isoformat(),
                "title": r.title,
                "metadata": dict(r.event_metadata or {}),
            }
            for r in rows
        ]
