"""Celery worker bootstrap for profile engine."""

from shared.celery_app import celery_app

# Ensure profile tasks are imported by worker process.
from services.profile_engine.tasks import profile_tasks  # noqa: F401
import services.generation.tasks  # noqa: F401  # registers generation Celery tasks

__all__ = ["celery_app"]
