"""Read source rows from PostgreSQL for warehouse sync."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.db import Ad, AdPerformance, CreativeFingerprint


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "hex"):  # UUID
        return str(value)
    return value


def _serialize_row(model: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in model.__table__.columns:
        key = col.name
        val = getattr(model, col.key)
        out[key] = _to_jsonable(val)
    return out


def read_ads(session: Session, since: datetime | None = None) -> list[dict[str, Any]]:
    stmt = select(Ad)
    if since is not None:
        stmt = stmt.where(Ad.updated_at > since)
    rows = session.scalars(stmt).all()
    return [_serialize_row(row) for row in rows]


def read_performance(session: Session, since: datetime | None = None) -> list[dict[str, Any]]:
    stmt = select(AdPerformance)
    if since is not None:
        # table has no updated_at in Phase 1 schema; use date as coarse fallback
        stmt = stmt.where(AdPerformance.date > since.date())
    rows = session.scalars(stmt).all()
    return [_serialize_row(row) for row in rows]


def read_fingerprints(session: Session, since: datetime | None = None) -> list[dict[str, Any]]:
    stmt = select(CreativeFingerprint)
    if since is not None:
        stmt = stmt.where(CreativeFingerprint.updated_at > since)
    rows = session.scalars(stmt).all()
    return [_serialize_row(row) for row in rows]
