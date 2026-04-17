"""PostgreSQL -> Snowflake sync orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import structlog
from sqlalchemy.orm import Session

from services.ingestion.connectors import postgres_reader, snowflake_writer
from services.ingestion.state_store import get_last_synced_at, set_last_synced_at

log = structlog.get_logger()

TableKey = Literal["ads", "ad_performance", "creative_fingerprints"]
Mode = Literal["full", "incremental"]


@dataclass
class SyncResult:
    table: TableKey
    mode: Mode
    records_read: int
    records_written: int
    last_synced_at: datetime | None


def _get_sync_session():
    from shared.utils.db_sync import sync_session

    return sync_session


def check_snowflake() -> None:
    snowflake_writer.check_connectivity()


def run_sync(table: TableKey, mode: Mode) -> SyncResult:
    with _get_sync_session()() as session:
        if table == "ads":
            return _run_ads(session, mode)
        if table == "ad_performance":
            return _run_performance(session, mode)
        return _run_fingerprints(session, mode)


def _run_ads(session: Session, mode: Mode) -> SyncResult:
    since = None if mode == "full" else get_last_synced_at(session, "ads")
    rows = postgres_reader.read_ads(session, since=since)
    written = (
        snowflake_writer.full_sync("ads", rows)
        if mode == "full"
        else snowflake_writer.incremental_upsert("ads", rows)
    )
    sync_ts = datetime.now(timezone.utc)
    set_last_synced_at(session, "ads", sync_ts)
    log.info("sync_done", table="ads", mode=mode, read=len(rows), written=written)
    return SyncResult("ads", mode, len(rows), written, sync_ts)


def _run_performance(session: Session, mode: Mode) -> SyncResult:
    since = None if mode == "full" else get_last_synced_at(session, "ad_performance")
    rows = postgres_reader.read_performance(session, since=since)
    written = (
        snowflake_writer.full_sync("ad_performance", rows)
        if mode == "full"
        else snowflake_writer.incremental_upsert("ad_performance", rows)
    )
    sync_ts = datetime.now(timezone.utc)
    set_last_synced_at(session, "ad_performance", sync_ts)
    log.info(
        "sync_done", table="ad_performance", mode=mode, read=len(rows), written=written
    )
    return SyncResult("ad_performance", mode, len(rows), written, sync_ts)


def _run_fingerprints(session: Session, mode: Mode) -> SyncResult:
    since = None if mode == "full" else get_last_synced_at(session, "creative_fingerprints")
    rows = postgres_reader.read_fingerprints(session, since=since)
    written = (
        snowflake_writer.full_sync("creative_fingerprints", rows)
        if mode == "full"
        else snowflake_writer.incremental_upsert("creative_fingerprints", rows)
    )
    sync_ts = datetime.now(timezone.utc)
    set_last_synced_at(session, "creative_fingerprints", sync_ts)
    log.info(
        "sync_done",
        table="creative_fingerprints",
        mode=mode,
        read=len(rows),
        written=written,
    )
    return SyncResult("creative_fingerprints", mode, len(rows), written, sync_ts)
