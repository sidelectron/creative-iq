"""Categorical statistical scorer for brand attribute values."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any


@dataclass
class CategoricalScore:
    """Scored categorical attribute value."""

    score: float
    confidence: float
    sample_size: int
    ci_lower: float
    ci_upper: float
    rank: int
    confidence_label: str


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _t_interval(mean: float, stddev: float, n: int) -> tuple[float, float]:
    if n <= 1 or stddev <= 0:
        return (mean, mean)
    margin = 1.96 * (stddev / sqrt(float(n)))
    return (mean - margin, mean + margin)


def _wilson_interval(successes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    spread = z * sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n) / denom
    return (center - spread, center + spread)


def _compute_confidence(score: float, ci_lower: float, ci_upper: float, n: int) -> float:
    if score <= 0:
        return 0.0
    width = max(0.0, ci_upper - ci_lower)
    base = 1.0 - (width / max(2.0 * score, 1e-6))
    sample_factor = min(1.0, sqrt(max(n, 0)) / 20.0)
    return _clamp(base * sample_factor, 0.0, 1.0)


def score_categorical_rows(
    rows: list[dict[str, Any]],
    *,
    metric: str,
) -> dict[str, dict[str, CategoricalScore]]:
    """Score categorical values grouped by attribute name/value."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        attr_name = str(row.get("attribute_name") or "")
        if not attr_name:
            continue
        grouped.setdefault(attr_name, []).append(row)

    out: dict[str, dict[str, CategoricalScore]] = {}
    for attr_name, attr_rows in grouped.items():
        scored: list[tuple[str, CategoricalScore]] = []
        for row in attr_rows:
            value = str(row.get("attribute_value") or "unknown")
            n = int(row.get("sample_size") or 0)
            score = float(row.get(f"performance_index_{metric}", row.get("score") or 1.0) or 1.0)
            stddev = float(row.get("stddev_metric_value") or row.get("metric_stddev") or 0.0)
            ci_method = str(row.get("ci_method") or "").lower()
            if ci_method == "wilson":
                successes = float(row.get("success_count") or 0.0)
                ci_lower, ci_upper = _wilson_interval(successes, max(n, 1))
                # Convert to performance-index-like space when baseline exists.
                baseline = float(row.get("brand_metric_avg") or 1.0)
                if baseline > 0:
                    ci_lower /= baseline
                    ci_upper /= baseline
            else:
                ci_lower, ci_upper = _t_interval(score, stddev, n)
            confidence = _compute_confidence(score, ci_lower, ci_upper, n)
            label = "high" if confidence >= 0.7 else ("medium" if confidence >= 0.4 else "low")
            scored.append(
                (
                    value,
                    CategoricalScore(
                        score=score,
                        confidence=confidence,
                        sample_size=n,
                        ci_lower=ci_lower,
                        ci_upper=ci_upper,
                        rank=0,
                        confidence_label=label,
                    ),
                )
            )
        scored.sort(key=lambda item: item[1].score, reverse=True)
        attr_payload: dict[str, CategoricalScore] = {}
        for idx, (value, payload) in enumerate(scored, start=1):
            payload.rank = idx
            attr_payload[value] = payload
        out[attr_name] = attr_payload
    return out
