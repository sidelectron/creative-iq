"""Airflow DAG: incremental PostgreSQL -> Snowflake RAW sync."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from services.ingestion.sync_service import check_snowflake, run_sync


default_args = {
    "owner": "creativeiq",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _sync_ads() -> None:
    run_sync("ads", "incremental")


def _sync_performance() -> None:
    run_sync("ad_performance", "incremental")


def _sync_fingerprints() -> None:
    run_sync("creative_fingerprints", "incremental")


with DAG(
    dag_id="dag_sync_pg_sf",
    default_args=default_args,
    schedule_interval="0 */2 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["creativeiq", "sync", "snowflake"],
) as dag:
    check_conn = PythonOperator(
        task_id="check_snowflake_connectivity",
        python_callable=check_snowflake,
    )

    sync_ads = PythonOperator(task_id="sync_ads", python_callable=_sync_ads)
    sync_performance = PythonOperator(
        task_id="sync_performance", python_callable=_sync_performance
    )
    sync_fingerprints = PythonOperator(
        task_id="sync_fingerprints", python_callable=_sync_fingerprints
    )

    check_conn >> [sync_ads, sync_performance, sync_fingerprints]

