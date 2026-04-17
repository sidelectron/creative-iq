"""Airflow DAG for scheduled profile recomputation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import select

from shared.models.db import Brand, BrandProfile
from shared.utils.db_sync import sync_session
from services.profile_engine.orchestrator.compute_profile import compute_brand_profile
from services.profile_engine.storage.repositories import snowflake_query

default_args = {
    "owner": "creativeiq",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _compute_stale_profiles() -> None:
    with sync_session() as session:
        brands = session.scalars(select(Brand).where(Brand.deleted_at.is_(None))).all()
        for brand in brands:
            for platform in ["meta", "tiktok", "youtube", "instagram"]:
                latest = session.scalar(
                    select(BrandProfile).where(
                        BrandProfile.brand_id == brand.id,
                        BrandProfile.platform == platform,
                        BrandProfile.audience_segment == "all",
                    )
                )
                stale = latest is None or (
                    datetime.now(timezone.utc) - latest.computed_at > timedelta(hours=24)
                )
                if not stale:
                    continue
                mart = snowflake_query(
                    """
                    SELECT MAX(computed_at) AS max_computed_at
                    FROM MARTS.MART_BRAND_OVERVIEW
                    WHERE brand_id = %s AND platform = %s
                    """,
                    (str(brand.id), platform),
                )
                mart_ts = mart[0].get("max_computed_at") if mart else None
                if latest is not None and mart_ts is not None and mart_ts <= latest.computed_at:
                    continue
                compute_brand_profile(session, brand.id, platform)


with DAG(
    dag_id="dag_profile_compute",
    default_args=default_args,
    schedule_interval="0 3 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["creativeiq", "profile"],
) as dag:
    compute_stale = PythonOperator(
        task_id="compute_stale_profiles",
        python_callable=_compute_stale_profiles,
    )

