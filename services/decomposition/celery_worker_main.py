"""Celery worker entry: imports task modules (heavy deps) without loading the API."""

from shared.celery_app import celery_app

import services.decomposition.tasks  # noqa: F401, E402 — register tasks

__all__ = ["celery_app"]
