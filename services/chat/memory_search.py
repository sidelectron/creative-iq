"""Semantic search over brand events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.models.db import BrandEra
from shared.utils.gemini import embed_text


def search_events(
    session: Session,
    *,
    brand_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict]:
    query_vector = embed_text(text=query)
    vector_literal = "[" + ",".join(f"{v:.8f}" for v in query_vector) + "]"
    params: dict[str, object] = {
        "brand_id": brand_id,
        "top_k": top_k,
        "embedding": vector_literal,
        "start_date": start_date,
        "end_date": end_date,
    }
    rows = session.execute(
        text(
            """
            SELECT
                id,
                event_type,
                title,
                description,
                source,
                event_date,
                metadata,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM brand_events
            WHERE brand_id = :brand_id
              AND embedding IS NOT NULL
              AND (:start_date IS NULL OR event_date >= :start_date)
              AND (:end_date IS NULL OR event_date <= :end_date)
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        ),
        params,
    ).mappings()
    eras = list(
        session.query(BrandEra)
        .filter(BrandEra.brand_id == brand_id)
        .order_by(BrandEra.start_date.asc())
        .all()
    )
    out: list[dict] = []
    for row in rows:
        era = None
        for item in eras:
            if item.start_date <= row["event_date"] and (item.end_date is None or item.end_date >= row["event_date"]):
                era = {
                    "id": str(item.id),
                    "name": item.era_name,
                    "start_date": item.start_date.isoformat(),
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                }
                break
        out.append(
            {
                "event_id": row["id"],
                "event_type": row["event_type"],
                "title": row["title"],
                "description": row["description"],
                "source": row["source"],
                "event_date": row["event_date"],
                "metadata": dict(row["metadata"] or {}),
                "similarity": max(0.0, min(1.0, float(row["similarity"] or 0.0))),
                "era": era,
            }
        )
    return out


def verify_vector_search_ready(session: Session) -> dict[str, bool]:
    checks = {"extension": False, "index": False}
    ext = session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
    checks["extension"] = ext is not None
    idx = session.execute(
        text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE tablename = 'brand_events'
              AND indexname = 'ix_brand_events_embedding_hnsw'
            """
        )
    ).first()
    checks["index"] = idx is not None
    return checks
