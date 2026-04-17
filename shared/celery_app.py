"""Shared Celery application (API dispatches tasks; worker consumes)."""

from __future__ import annotations

from celery import Celery

from shared.config.settings import settings

celery_app = Celery(
    "creativeiq",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_soft_time_limit=300,
    task_time_limit=360,
    task_acks_late=True,
    task_default_queue="decomposition",
    task_routes={
        "services.decomposition.tasks.decompose_ad": {"queue": "decomposition"},
        "services.decomposition.tasks.decomposition_health": {"queue": "decomposition"},
        "services.profile_engine.tasks.profile_tasks.compute_profile": {"queue": "profile"},
        "services.profile_engine.tasks.profile_tasks.detect_drift": {"queue": "profile"},
        "services.profile_engine.tasks.profile_tasks.consume_marts_refresh": {"queue": "profile"},
        "services.generation.tasks.run_generation_job": {"queue": "generation"},
    },
    beat_schedule={
        "profile-consume-marts-refresh": {
            "task": "services.profile_engine.tasks.profile_tasks.consume_marts_refresh",
            "schedule": 60.0,
        }
    },
    worker_prefetch_multiplier=1,
)
