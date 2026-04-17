"""Continuous attribute scorer."""

from __future__ import annotations

from typing import Any


def score_continuous_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build continuous attribute analysis payload from mart rows."""
    out: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("attribute_name") or ""), []).append(row)

    for attr_name, attr_rows in grouped.items():
        if not attr_name:
            continue
        first = attr_rows[0]
        corr = float(first.get("correlation") or 0.0)
        p_value = float(first.get("p_value") or 1.0)
        bins: list[dict[str, Any]] = []
        for row in attr_rows:
            bins.append(
                {
                    "bin_lower": float(row.get("bin_lower") or 0.0),
                    "bin_upper": float(row.get("bin_upper") or 0.0),
                    "performance_score": float(row.get("performance_score") or 0.0),
                    "sample_size": int(row.get("sample_size") or 0),
                }
            )
        bins.sort(key=lambda b: (b["bin_lower"], b["bin_upper"]))
        best = max(bins, key=lambda b: b["performance_score"]) if bins else None
        best_idx = bins.index(best) if best else -1
        mid_idx = len(bins) // 2
        is_non_linear = bool(
            len(bins) >= 3
            and best_idx == mid_idx
            and abs(corr) < 0.15
            and p_value >= 0.05
        )
        out[attr_name] = {
            "correlation": corr,
            "p_value": p_value,
            "is_significant": p_value < 0.05,
            "optimal_range": (
                (best["bin_lower"], best["bin_upper"]) if best else (None, None)
            ),
            "optimal_range_score": (best["performance_score"] if best else None),
            "is_non_linear": is_non_linear,
            "bins": bins,
        }
    return out
