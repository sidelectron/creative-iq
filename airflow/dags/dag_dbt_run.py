"""Airflow DAG: dbt staging -> intermediate -> marts -> tests."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

from shared.utils.redis_sync import publish_event_sync

DBT_PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/project/dbt_project")


default_args = {
    "owner": "creativeiq",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _run_dbt(select_tag: str) -> None:
    cmd = ["dbt", "run", "--select", select_tag]
    proc = subprocess.run(cmd, cwd=DBT_PROJECT_DIR, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"dbt run failed for {select_tag}")


def _run_tests() -> None:
    cmd = ["dbt", "test", "--select", "staging,intermediate,marts"]
    proc = subprocess.run(cmd, cwd=DBT_PROJECT_DIR, check=False)
    if proc.returncode != 0:
        # Phase 3 asks for warning-style alert; hard fail DAG after warning
        raise RuntimeError("dbt tests failed (warning alert emitted in task logs)")


def _publish_refresh_event() -> None:
    publish_event_sync(
        {"event": "dbt.marts_refreshed", "timestamp": datetime.now(timezone.utc).isoformat()}
    )


with DAG(
    dag_id="dag_dbt_run",
    default_args=default_args,
    schedule_interval="30 */2 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["creativeiq", "dbt"],
) as dag:
    wait_for_sync = ExternalTaskSensor(
        task_id="wait_for_sync",
        external_dag_id="dag_sync_pg_sf",
        external_task_id=None,
        timeout=60 * 60,
        poke_interval=60,
        mode="reschedule",
    )

    run_staging = PythonOperator(
        task_id="run_staging", python_callable=_run_dbt, op_kwargs={"select_tag": "staging"}
    )
    run_intermediate = PythonOperator(
        task_id="run_intermediate",
        python_callable=_run_dbt,
        op_kwargs={"select_tag": "intermediate"},
    )
    run_marts = PythonOperator(
        task_id="run_marts", python_callable=_run_dbt, op_kwargs={"select_tag": "marts"}
    )
    run_dbt_tests = PythonOperator(task_id="run_dbt_tests", python_callable=_run_tests)
    publish_event = PythonOperator(
        task_id="publish_marts_refreshed_event", python_callable=_publish_refresh_event
    )

    wait_for_sync >> run_staging >> run_intermediate >> run_marts >> run_dbt_tests >> publish_event

