"""Celery tasks for decomposition."""

from __future__ import annotations

import uuid

import structlog
from celery import Task
from celery.signals import worker_ready

from shared.celery_app import celery_app
from shared.models.db import Ad
from shared.models.enums import AdStatus
from shared.utils.db_sync import sync_session
from services.decomposition.pipeline.orchestrator import PermanentPipelineError, run_decomposition

log = structlog.get_logger()


class TransientDecompositionError(Exception):
    """Transient failure eligible for Celery retry (non-permanent pipeline)."""


@celery_app.task(
    bind=True,
    name="services.decomposition.tasks.decompose_ad",
    acks_late=True,
)
def decompose_ad(self: Task, ad_id: str) -> None:
    aid = uuid.UUID(ad_id)
    task_id = self.request.id or "unknown"

    with sync_session() as session:
        ad = session.get(Ad, aid)
        if ad is None or ad.deleted_at is not None:
            return

        meta = dict(ad.ad_metadata or {})
        prev_task = meta.get("decomposition_celery_task_id")

        if ad.status == AdStatus.DECOMPOSING.value:
            if prev_task in (task_id, None):
                try:
                    run_decomposition(session, aid, task_id)
                except PermanentPipelineError:
                    return
                except Exception as exc:  # noqa: BLE001
                    _maybe_retry(self, exc)
                return
            log.info("decompose_skip_concurrent", ad_id=ad_id, task_id=task_id)
            return

        if ad.status not in (
            AdStatus.INGESTED.value,
            AdStatus.FAILED.value,
            AdStatus.DECOMPOSED.value,
        ):
            log.info("decompose_skip_status", ad_id=ad_id, status=ad.status)
            return

        ad.status = AdStatus.DECOMPOSING.value
        meta["decomposition_celery_task_id"] = task_id
        ad.ad_metadata = meta
        session.add(ad)
        session.commit()

    with sync_session() as session:
        try:
            run_decomposition(session, aid, task_id)
        except PermanentPipelineError:
            return
        except Exception as exc:  # noqa: BLE001
            _maybe_retry(self, exc)


def _maybe_retry(self: Task, exc: Exception) -> None:
    if self.request.retries >= 3:
        raise exc
    if isinstance(exc, (ConnectionError, TimeoutError, OSError, TransientDecompositionError)):
        delays = [10, 30, 90]
        countdown = delays[min(self.request.retries, 2)]
        raise self.retry(exc=exc, countdown=countdown) from exc
    raise exc


@celery_app.task(name="services.decomposition.tasks.decomposition_health")
def decomposition_health() -> str:
    return "ok"


@worker_ready.connect
def _start_prometheus(**kwargs: object) -> None:
    try:
        from services.decomposition.metrics import start_metrics_server

        start_metrics_server()
    except OSError:
        pass
