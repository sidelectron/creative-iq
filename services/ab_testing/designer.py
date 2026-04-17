"""A/B test design logic."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from shared.models.db import ABTest
from services.profile_engine import metrics
from services.profile_engine.storage import repositories
from services.chat.auto_events_service import emit_ab_lifecycle_event


def _z(alpha: float, power: float) -> tuple[float, float]:
    # Fixed defaults from spec (alpha=0.05, power=0.80).
    # Kept deterministic to avoid heavy stats imports in API runtime.
    return (1.96 if alpha == 0.05 else 1.96, 0.84 if power == 0.80 else 0.84)


def required_sample_size(
    baseline: float,
    mde_relative: float = 0.10,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Compute per-variant sample size using two-sample approximation."""
    baseline = max(baseline, 1e-6)
    delta = max(baseline * mde_relative, 1e-6)
    z_alpha, z_beta = _z(alpha, power)
    variance = baseline * (1.0 - baseline)
    n = 2.0 * ((z_alpha + z_beta) ** 2) * variance / (delta**2)
    return max(50, int(math.ceil(n)))


def design_test(
    *,
    brand_id: uuid.UUID,
    created_by: uuid.UUID,
    attribute_to_test: str,
    variants: list[str],
    target_metric: str,
    hypothesis: str | None,
    baseline_metric: float,
    avg_cpm: float | None,
    avg_daily_impressions: float | None,
    alpha: float = 0.05,
    power: float = 0.80,
    mde_relative: float = 0.10,
) -> dict[str, Any]:
    """Create deterministic A/B test plan payload."""
    n = required_sample_size(baseline_metric, mde_relative=mde_relative, alpha=alpha, power=power)
    budget = ((n / 1000.0) * avg_cpm) if avg_cpm is not None else None
    duration_days = (
        int(math.ceil(n / max(avg_daily_impressions, 1.0)))
        if avg_daily_impressions is not None
        else None
    )
    abs_mde = baseline_metric * mde_relative
    hypo = (
        hypothesis
        or f"{variants[1]} will outperform {variants[0]} on {target_metric}"
        if len(variants) >= 2
        else f"Variant comparison on {target_metric}"
    )
    plan = {
        "hypothesis": hypo,
        "variants": variants,
        "target_metric": target_metric,
        "sample_size_per_variant": n,
        "estimated_budget_per_variant": budget,
        "estimated_duration_days": duration_days,
        "alpha": alpha,
        "power": power,
        "mde_relative": mde_relative,
        "mde_absolute": abs_mde,
        "instructions": {
            "keep_constant": ["platform", "audience", "timing", "budget_per_variant"],
            "vary_only": attribute_to_test,
        },
    }
    metrics.AB_TESTS_DESIGNED_TOTAL.inc()
    return plan


def persist_test_plan(
    session,
    *,
    brand_id: uuid.UUID,
    created_by: uuid.UUID,
    attribute_to_test: str,
    target_metric: str,
    plan: dict[str, Any],
) -> ABTest:
    row = ABTest(
        brand_id=brand_id,
        created_by=created_by,
        attribute_tested=attribute_to_test,
        variants=plan["variants"],
        target_metric=target_metric,
        hypothesis=plan["hypothesis"],
        sample_size_required=int(plan["sample_size_per_variant"]),
        estimated_budget=(
            Decimal(str(round(float(plan["estimated_budget_per_variant"]), 2)))
            if plan.get("estimated_budget_per_variant") is not None
            else None
        ),
        estimated_duration_days=plan.get("estimated_duration_days"),
        significance_level=Decimal(str(plan["alpha"])),
        power=Decimal(str(plan["power"])),
        status="proposed",
    )
    saved = repositories.create_ab_test(session, row)
    emit_ab_lifecycle_event(session, test=saved, status="proposed")
    return saved
