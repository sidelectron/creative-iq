"""Temporal and era-aware weighting helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from math import exp, log
from typing import Any


HALF_LIFE_DAYS = 140.0
DECAY_RATE = log(2.0) / HALF_LIFE_DAYS


def compute_temporal_weight(published_at: datetime | None, now: datetime) -> float:
    """Compute exponential decay weight by ad age."""
    if published_at is None:
        return 0.25
    pub = published_at.astimezone(timezone.utc)
    delta_days = max(0.0, (now - pub).total_seconds() / 86400.0)
    return exp(-DECAY_RATE * delta_days)


def era_multiplier(published_at: datetime | None, eras: list[dict[str, Any]]) -> float:
    """Return era multiplier using current/previous/older weighting."""
    if published_at is None or not eras:
        return 1.0
    pub = published_at.astimezone(timezone.utc)
    ordered = sorted(eras, key=lambda e: e["start_date"])
    current_idx = len(ordered) - 1
    matched_idx = None
    for idx, era in enumerate(ordered):
        start = era["start_date"]
        end = era.get("end_date")
        if pub >= start and (end is None or pub <= end):
            matched_idx = idx
            break
    if matched_idx is None:
        return 0.1
    distance = current_idx - matched_idx
    if distance <= 0:
        return 1.0
    if distance == 1:
        return 0.3
    return 0.1


def normalized_row_weights(
    rows: list[dict[str, Any]],
    eras: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[float]:
    """Compute normalized combined temporal + era weights."""
    now_ts = now or datetime.now(timezone.utc)
    raw: list[float] = []
    for row in rows:
        pub = row.get("published_at")
        temporal = compute_temporal_weight(pub, now_ts)
        multiplier = era_multiplier(pub, eras)
        raw.append(temporal * multiplier)
    total = sum(raw)
    if total <= 0:
        return [1.0 / max(len(rows), 1)] * len(rows)
    return [w / total for w in raw]
