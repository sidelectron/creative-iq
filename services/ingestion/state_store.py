"""Sync watermark storage in PostgreSQL sync_state table."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.db import SyncState


def get_last_synced_at(session: Session, table_name: str) -> datetime | None:
    row = session.scalar(select(SyncState).where(SyncState.table_name == table_name))
    return row.last_synced_at if row else None


def set_last_synced_at(session: Session, table_name: str, value: datetime | None = None) -> None:
    ts = value or datetime.now(timezone.utc)
    row = session.scalar(select(SyncState).where(SyncState.table_name == table_name))
    if row is None:
        row = SyncState(table_name=table_name, last_synced_at=ts)
        session.add(row)
    else:
        row.last_synced_at = ts
        session.add(row)
    session.commit()
