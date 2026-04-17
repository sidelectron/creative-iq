from __future__ import annotations

import uuid
from types import SimpleNamespace

from services.profile_engine.drift.detector import detect_drift_for_brand


def test_drift_detector_skips_when_data_span_under_30(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.get_latest_profile",
        lambda session, brand_id, platform: SimpleNamespace(profile_data={"categorical": {}}),
    )
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.get_brand_data_span_days",
        lambda brand_id, platform: 10,
    )
    alerts = detect_drift_for_brand(object(), uuid.uuid4(), "meta")
    assert alerts == []


def test_drift_detector_dedup_prevents_duplicate_alert(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.get_latest_profile",
        lambda session, brand_id, platform: SimpleNamespace(
            profile_data={
                "categorical": {"hook_type": {"testimonial": {"score": 1.0}}}
            }
        ),
    )
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.get_brand_data_span_days",
        lambda brand_id, platform: 45,
    )
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.snowflake_query",
        lambda q, params, query_type="generic": [
            {
                "attribute_name": "hook_type",
                "attribute_value": "testimonial",
                "recent_score": 1.4,
                "recent_sample_size": 20,
            }
        ],
    )
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.drift_alert_exists",
        lambda session, brand_id, attribute_key, min_event_date: True,
    )
    inserted: list[dict] = []
    monkeypatch.setattr(
        "services.profile_engine.drift.detector.repositories.insert_brand_event",
        lambda *args, **kwargs: inserted.append(kwargs),
    )
    alerts = detect_drift_for_brand(object(), uuid.uuid4(), "meta")
    assert alerts == []
    assert inserted == []
