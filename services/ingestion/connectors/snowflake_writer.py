"""Snowflake writer using snowflake-connector-python (write_pandas + batch insert fallback)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from shared.config.settings import settings


RAW_SCHEMA = settings.snowflake_schema_raw.upper()


TABLE_CONFIG: dict[str, dict[str, Any]] = {
    "ads": {
        "target": "ADS",
        "json_cols": {"metadata"},
        "pk": ["id"],
    },
    "ad_performance": {
        "target": "AD_PERFORMANCE",
        "json_cols": {"metadata"},
        "pk": ["ad_id", "date"],
    },
    "creative_fingerprints": {
        "target": "CREATIVE_FINGERPRINTS",
        "json_cols": {"attributes", "low_level_features", "gemini_analysis"},
        "pk": ["ad_id"],
    },
}


def _connect():
    import snowflake.connector

    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        role=settings.snowflake_role,
        schema=RAW_SCHEMA,
    )


def check_connectivity() -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_TIMESTAMP()")
            cur.fetchone()
    finally:
        conn.close()


def _prepare_rows(table_key: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cfg = TABLE_CONFIG[table_key]
    out: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        for c in cfg["json_cols"]:
            if c in r and r[c] is not None:
                r[c] = json.dumps(r[c], sort_keys=True, default=str)
        r["loaded_at"] = datetime.now(timezone.utc).isoformat()
        out.append(r)
    return out


def full_sync(table_key: str, rows: list[dict[str, Any]]) -> int:
    conn = _connect()
    cfg = TABLE_CONFIG[table_key]
    target = cfg["target"]
    prepared = _prepare_rows(table_key, rows)
    try:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {RAW_SCHEMA}.{target}")
        return _load_dataframe(conn, target, prepared)
    finally:
        conn.close()


def incremental_upsert(table_key: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    conn = _connect()
    cfg = TABLE_CONFIG[table_key]
    target = cfg["target"]
    prepared = _prepare_rows(table_key, rows)
    stage_table = f"{target}_STAGE_SYNC"
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE TEMP TABLE IF NOT EXISTS {stage_table} LIKE {RAW_SCHEMA}.{target}")
            cur.execute(f"TRUNCATE TABLE {stage_table}")
        _load_dataframe(conn, stage_table, prepared, create_temp=False)
        pk = cfg["pk"]
        all_cols = list(prepared[0].keys())
        set_cols = [c for c in all_cols if c not in pk]
        on_clause = " AND ".join([f"T.{k} = S.{k}" for k in pk])
        set_clause = ", ".join([f"{c}=S.{c}" for c in set_cols])
        insert_cols = ", ".join(all_cols)
        insert_vals = ", ".join([f"S.{c}" for c in all_cols])
        merge_sql = f"""
        MERGE INTO {RAW_SCHEMA}.{target} T
        USING {stage_table} S
          ON {on_clause}
        WHEN MATCHED THEN UPDATE SET {set_clause}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
        """
        with conn.cursor() as cur:
            cur.execute(merge_sql)
            cur.execute(f"DROP TABLE IF EXISTS {stage_table}")
        return len(prepared)
    finally:
        conn.close()


def _load_dataframe(
    conn,
    table_name: str,
    rows: list[dict[str, Any]],
    create_temp: bool = False,
) -> int:
    if not rows:
        return 0
    import pandas as pd
    from snowflake.connector.pandas_tools import write_pandas

    df = pd.DataFrame(rows)
    ok, _, nrows, _ = write_pandas(
        conn,
        df,
        table_name=table_name,
        schema=None if create_temp else RAW_SCHEMA,
        auto_create_table=False,
        overwrite=False,
    )
    if ok:
        return int(nrows)

    # fallback to row-by-row insert when write_pandas fails
    cols = list(df.columns)
    col_sql = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO {table_name if create_temp else f'{RAW_SCHEMA}.{table_name}'} ({col_sql}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        cur.executemany(insert_sql, [tuple(r[c] for c in cols) for r in rows])
    return len(rows)
