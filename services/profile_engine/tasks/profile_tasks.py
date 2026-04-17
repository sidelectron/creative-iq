"""Celery tasks for profile computation and drift detection."""

from __future__ import annotations

import json
import uuid

from celery import Task
from celery.signals import worker_ready
from shared.celery_app import celery_app
from shared.config.settings import settings
from shared.utils.db_sync import sync_session
from shared.utils.redis_sync import get_redis_sync
from services.profile_engine.drift.detector import detect_drift_for_brand
from services.profile_engine.metrics import start_metrics_server
from services.profile_engine.orchestrator.compute_profile import compute_brand_profile
from services.profile_engine.storage import repositories


@celery_app.task(bind=True, name="services.profile_engine.tasks.profile_tasks.compute_profile")
def compute_profile_task(self: Task, brand_id: str, platform: str) -> dict:
    with sync_session() as session:
        return compute_brand_profile(session, uuid.UUID(brand_id), platform)


@celery_app.task(bind=True, name="services.profile_engine.tasks.profile_tasks.detect_drift")
def detect_drift_task(self: Task, brand_id: str, platform: str) -> list[dict]:
    with sync_session() as session:
        return detect_drift_for_brand(session, uuid.UUID(brand_id), platform)


@celery_app.task(bind=True, name="services.profile_engine.tasks.profile_tasks.consume_marts_refresh")
def consume_marts_refresh(self: Task) -> dict[str, int]:
    """Consume Redis stream and compute changed brand/platform profiles."""
    redis_client = get_redis_sync()
    state_key = "profile_engine:events:last_id"
    last_id = redis_client.get(state_key) or "0-0"
    messages = redis_client.xread({settings.redis_events_stream: last_id}, count=20, block=1000)
    consumed = 0
    computed = 0
    for _, entries in messages:
        for message_id, payload in entries:
            consumed += 1
            raw = payload.get("payload")
            try:
                event = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                event = {}
            if event.get("event") == "dbt.marts_refreshed":
                with sync_session() as session:
                    changed = repositories.list_changed_brand_platforms(session)
                    for brand_id, platform in changed:
                        compute_brand_profile(session, brand_id, platform)
                        computed += 1
            redis_client.set(state_key, message_id)
    return {"events_consumed": consumed, "profiles_computed": computed}


@worker_ready.connect
def _start_profile_metrics(**kwargs: object) -> None:
    try:
        start_metrics_server()
    except OSError:
        pass
