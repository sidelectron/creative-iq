"""Auto-detected events for drift, A/B lifecycle, novelty, and outliers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.db import ABTest, Ad, AdPerformance, BrandEvent, CreativeFingerprint
from shared.models.enums import EventSource
from services.chat.events_service import create_event


def emit_ab_lifecycle_event(session: Session, *, test: ABTest, status: str) -> None:
    event_type = f"ab_test_{status}"
    create_event(
        session,
        brand_id=test.brand_id,
        event_type=event_type,
        title=f"A/B test {status}: {test.attribute_tested}",
        event_date=datetime.now(timezone.utc),
        description=test.hypothesis,
        impact_tags=[test.target_metric],
        source=EventSource.AUTO_DETECTED.value,
        metadata={"test_id": str(test.id), "status": status},
    )


def detect_style_novelty_for_ad(session: Session, *, ad_id: uuid.UUID) -> None:
    fp = session.scalar(select(CreativeFingerprint).where(CreativeFingerprint.ad_id == ad_id))
    ad = session.get(Ad, ad_id)
    if fp is None or ad is None:
        return
    visual_style = str((fp.attributes or {}).get("visual_style", "")).strip()
    if not visual_style:
        return
    prior_rows = session.scalars(
        select(BrandEvent).where(
            BrandEvent.brand_id == ad.brand_id,
            BrandEvent.event_type == "style_novelty",
            BrandEvent.source == EventSource.AUTO_DETECTED.value,
        )
    ).all()
    seen = {
        str((row.event_metadata or {}).get("visual_style", "")).strip().lower() for row in prior_rows
    }
    if visual_style.lower() in seen:
        return
    create_event(
        session,
        brand_id=ad.brand_id,
        event_type="style_novelty",
        title=f"New visual style detected: {visual_style}",
        event_date=datetime.now(timezone.utc),
        description=f"First seen on ad {ad_id}",
        impact_tags=[ad.platform],
        source=EventSource.AUTO_DETECTED.value,
        metadata={"visual_style": visual_style, "ad_id": str(ad_id), "platform": ad.platform},
    )


def detect_single_ad_outlier(session: Session, *, ad_id: uuid.UUID) -> None:
    ad = session.get(Ad, ad_id)
    if ad is None:
        return
    rows = list(session.scalars(select(AdPerformance).where(AdPerformance.ad_id == ad_id)).all())
    if not rows:
        return
    ctrs = [r.ctr for r in rows if r.ctr is not None]
    if len(ctrs) < 2:
        return
    mean = sum(ctrs) / len(ctrs)
    variance = sum((v - mean) ** 2 for v in ctrs) / max(1, len(ctrs) - 1)
    std = variance**0.5
    latest = ctrs[-1]
    if std <= 0 or abs(latest - mean) < (3.0 * std):
        return
    create_event(
        session,
        brand_id=ad.brand_id,
        event_type="single_ad_outlier",
        title=f"Outlier detected for ad {ad_id}",
        event_date=datetime.now(timezone.utc),
        description=f"Latest CTR {latest:.4f} deviates from mean {mean:.4f}.",
        impact_tags=[ad.platform, "ctr"],
        source=EventSource.AUTO_DETECTED.value,
        metadata={"ad_id": str(ad_id), "z_threshold": 3.0, "mean_ctr": mean, "latest_ctr": latest},
    )
