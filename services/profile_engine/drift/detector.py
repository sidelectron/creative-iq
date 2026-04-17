"""Profile drift detector."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from services.profile_engine import metrics
from services.profile_engine.storage import repositories


def detect_drift_for_brand(
    session: Session,
    brand_id: uuid.UUID,
    platform: str,
    *,
    relative_threshold: float = 0.20,
    min_recent_sample_size: int = 10,
) -> list[dict[str, Any]]:
    """Detect drift by comparing historical profile with 30-day recent profile."""
    historical = repositories.get_latest_profile(session, brand_id, platform)
    if historical is None:
        return []
    if repositories.get_brand_data_span_days(brand_id, platform) < 30:
        return []
    recent_rows = repositories.snowflake_query(
        """
        SELECT attribute_name, attribute_value, recent_score, recent_sample_size
        FROM MARTS.MART_ATTRIBUTE_DRIFT_30D
        WHERE brand_id = %s AND platform = %s
        """,
        (str(brand_id), platform),
        query_type="drift_recent_window",
    )
    historical_scores: dict[str, float] = {}
    cat = (historical.profile_data or {}).get("categorical", {})
    for attr_name, values in cat.items():
        for value_name, payload in values.items():
            historical_scores[f"{attr_name}:{value_name}"] = float(payload.get("score", 0.0))

    alerts: list[dict[str, Any]] = []
    for row in recent_rows:
        key = f'{row.get("attribute_name")}:{row.get("attribute_value")}'
        historical_score = historical_scores.get(key)
        if historical_score is None or historical_score == 0:
            continue
        recent_score = float(row.get("recent_score") or 0.0)
        n_recent = int(row.get("recent_sample_size") or 0)
        if n_recent < min_recent_sample_size:
            continue
        rel_change = abs(recent_score - historical_score) / abs(historical_score)
        if rel_change < relative_threshold:
            continue
        direction = "improving" if recent_score > historical_score else "declining"
        alert = {
            "attribute_key": key,
            "historical_score": historical_score,
            "recent_score": recent_score,
            "direction": direction,
            "magnitude_relative": rel_change,
            "recent_sample_size": n_recent,
        }
        if repositories.drift_alert_exists(
            session,
            brand_id=brand_id,
            attribute_key=key,
            min_event_date=datetime.now(timezone.utc) - timedelta(days=1),
        ):
            continue
        repositories.insert_brand_event(
            session,
            brand_id=brand_id,
            event_type="performance_anomaly",
            title=f"Drift detected for {key}",
            description=f"Recent score changed by {rel_change:.1%} ({direction}).",
            source="auto_detected",
            metadata=alert,
        )
        metrics.DRIFT_ALERTS_TOTAL.labels(attribute_name=str(row.get("attribute_name"))).inc()
        alerts.append(alert)
    return alerts
