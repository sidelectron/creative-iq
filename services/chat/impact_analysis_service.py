"""Event impact analysis."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.models.db import BrandEvent
from shared.utils.gemini import GeminiError, generate_json


def analyze_event_impact(
    session: Session,
    *,
    brand_id: uuid.UUID,
    event_id: uuid.UUID,
    pre_days: int = 30,
    post_days: int = 30,
    force_recompute: bool = False,
) -> dict[str, Any] | None:
    row = session.get(BrandEvent, event_id)
    if row is None or row.brand_id != brand_id:
        return None
    meta = dict(row.event_metadata or {})
    cached = meta.get("impact_analysis")
    if cached and not force_recompute:
        payload = dict(cached)
        payload["cached"] = True
        return payload
    event_dt = row.event_date.astimezone(timezone.utc)
    pre_start = event_dt - timedelta(days=pre_days)
    post_end = event_dt + timedelta(days=post_days)
    perf = session.execute(
        text(
            """
            SELECT
                AVG(CASE WHEN p.date >= :pre_start::date AND p.date < :event_date::date THEN p.clicks * 1.0 / NULLIF(p.impressions, 0) END) AS pre_ctr,
                AVG(CASE WHEN p.date >= :event_date::date AND p.date <= :post_end::date THEN p.clicks * 1.0 / NULLIF(p.impressions, 0) END) AS post_ctr
            FROM ad_performance p
            JOIN ads a ON a.id = p.ad_id
            WHERE a.brand_id = :brand_id
            """
        ),
        {
            "pre_start": pre_start,
            "event_date": event_dt,
            "post_end": post_end,
            "brand_id": brand_id,
        },
    ).first()
    pre_ctr = float((perf.pre_ctr or 0.0) if perf else 0.0)
    post_ctr = float((perf.post_ctr or 0.0) if perf else 0.0)
    delta = post_ctr - pre_ctr
    significance = {"is_significant": abs(delta) >= 0.005, "threshold": 0.005}
    summary = (
        f"CTR changed from {pre_ctr:.4f} to {post_ctr:.4f} ({delta:+.4f}) around event {row.title}."
    )
    try:
        llm_payload, _, _ = generate_json(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": summary + " Return JSON {summary: string}"}]}],
            cache_key_parts={"impact_event": str(event_id), "pre_days": pre_days, "post_days": post_days},
        )
        summary = str(llm_payload.get("summary") or summary)
    except GeminiError:
        pass
    payload = {
        "event_id": str(event_id),
        "summary": summary,
        "pre_window": {"days": pre_days, "ctr": pre_ctr},
        "post_window": {"days": post_days, "ctr": post_ctr},
        "deltas": {"ctr": delta},
        "significance": significance,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }
    meta["impact_analysis"] = payload
    row.event_metadata = meta
    session.add(row)
    session.commit()
    return payload
