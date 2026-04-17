"""Airflow DAG for daily drift detection."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import select

from shared.models.db import Brand
from shared.utils.db_sync import sync_session
from services.profile_engine.drift.detector import detect_drift_for_brand

default_args = {
    "owner": "creativeiq",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _run_drift() -> None:
    with sync_session() as session:
        brands = session.scalars(select(Brand).where(Brand.deleted_at.is_(None))).all()
        for brand in brands:
            for platform in ["meta", "tiktok", "youtube", "instagram"]:
                detect_drift_for_brand(session, brand.id, platform)


with DAG(
    dag_id="dag_drift_detect",
    default_args=default_args,
    schedule_interval="30 3 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["creativeiq", "drift"],
) as dag:
    detect = PythonOperator(task_id="detect_drift", python_callable=_run_drift)
