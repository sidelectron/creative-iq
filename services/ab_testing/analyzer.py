"""A/B test analyzer logic (frequentist + Bayesian summary)."""

from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.db import ABTest, AdPerformance
from services.chat.auto_events_service import emit_ab_lifecycle_event
from services.profile_engine import metrics
from services.profile_engine.storage import repositories


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _mean(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def _sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mu = _mean(values)
    variance = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _welch_ttest(control_vals: list[float], treatment_vals: list[float]) -> tuple[float, float]:
    """Approximate Welch t-test; uses scipy when available, fallback normal approx."""
    try:
        from scipy import stats as scipy_stats

        t_stat, p_val = scipy_stats.ttest_ind(treatment_vals, control_vals, equal_var=False)
        return float(t_stat), float(p_val)
    except Exception:
        c_mean = _mean(control_vals)
        t_mean = _mean(treatment_vals)
        c_var = _sample_std(control_vals) ** 2
        t_var = _sample_std(treatment_vals) ** 2
        se = math.sqrt((c_var / max(len(control_vals), 1)) + (t_var / max(len(treatment_vals), 1)))
        if se <= 0:
            return 0.0, 1.0
        t_stat = (t_mean - c_mean) / se
        p_val = 2.0 * (1.0 - _normal_cdf(abs(t_stat)))
        return float(t_stat), float(p_val)


def _metric_value(metric: str, row: AdPerformance) -> float | None:
    metric = metric.lower()
    if metric == "ctr":
        return row.ctr
    if metric == "cpa":
        return row.cpa
    if metric == "roas":
        return row.roas
    return row.ctr


def _collect_variant_values(session: Session, ad_ids: list[str], metric: str) -> list[float]:
    ids = [uuid.UUID(v) for v in ad_ids]
    rows = session.scalars(select(AdPerformance).where(AdPerformance.ad_id.in_(ids))).all()
    out: list[float] = []
    for row in rows:
        value = _metric_value(metric, row)
        if value is not None:
            out.append(float(value))
    return out


def _collect_rate_counts(session: Session, ad_ids: list[str], metric: str) -> tuple[int, int]:
    ids = [uuid.UUID(v) for v in ad_ids]
    rows = session.scalars(select(AdPerformance).where(AdPerformance.ad_id.in_(ids))).all()
    if metric.lower() == "ctr":
        successes = sum(int(r.clicks) for r in rows)
        trials = sum(int(r.impressions) for r in rows)
    else:
        successes = sum(int(r.conversions) for r in rows)
        trials = sum(int(r.clicks) for r in rows)
    return successes, trials


def _bayesian_rate_probability(
    control_successes: int,
    control_trials: int,
    treatment_successes: int,
    treatment_trials: int,
) -> float:
    alpha_c = 1 + max(control_successes, 0)
    beta_c = 1 + max(control_trials - control_successes, 0)
    alpha_t = 1 + max(treatment_successes, 0)
    beta_t = 1 + max(treatment_trials - treatment_successes, 0)
    draws = 5000
    wins = 0
    for _ in range(draws):
        c_sample = random.betavariate(alpha_c, beta_c)
        t_sample = random.betavariate(alpha_t, beta_t)
        if t_sample > c_sample:
            wins += 1
    return float(wins / draws)


def _bayesian_normal_probability(control_vals: list[float], treatment_vals: list[float]) -> float:
    c_mean = _mean(control_vals)
    t_mean = _mean(treatment_vals)
    c_var = (_sample_std(control_vals) ** 2) if len(control_vals) > 1 else 0.0
    t_var = (_sample_std(treatment_vals) ** 2) if len(treatment_vals) > 1 else 0.0
    se = math.sqrt((c_var / max(len(control_vals), 1)) + (t_var / max(len(treatment_vals), 1)))
    if se <= 0:
        return 0.5
    z = (t_mean - c_mean) / se
    return float(_normal_cdf(z))


def analyze_test(session: Session, test: ABTest) -> dict[str, Any]:
    """Analyze completed A/B test and return result payload."""
    variants = list(test.variants or [])
    if len(variants) < 2:
        raise ValueError("At least two variants required")
    control = variants[0]
    treatment = variants[1]
    control_ids = list((control or {}).get("ad_ids", []))
    treatment_ids = list((treatment or {}).get("ad_ids", []))
    control_vals = _collect_variant_values(session, control_ids, test.target_metric)
    treatment_vals = _collect_variant_values(session, treatment_ids, test.target_metric)
    if len(control_vals) < 2 or len(treatment_vals) < 2:
        return {"status": "inconclusive", "reason": "insufficient_data"}

    t_stat, p_val = _welch_ttest(control_vals, treatment_vals)
    control_mean = _mean(control_vals)
    treatment_mean = _mean(treatment_vals)
    relative_effect = (treatment_mean - control_mean) / control_mean if control_mean else 0.0
    pooled_std = math.sqrt(
        (
            (((len(control_vals) - 1) * _sample_std(control_vals) ** 2))
            + (((len(treatment_vals) - 1) * _sample_std(treatment_vals) ** 2))
        )
        / (len(control_vals) + len(treatment_vals) - 2)
    )
    cohens_d = ((treatment_mean - control_mean) / pooled_std) if pooled_std else 0.0
    if test.target_metric.lower() in {"ctr", "conversion_rate"}:
        cs, ct = _collect_rate_counts(session, control_ids, test.target_metric)
        ts, tt = _collect_rate_counts(session, treatment_ids, test.target_metric)
        bayes_prob_treatment_better = _bayesian_rate_probability(cs, ct, ts, tt)
        bayesian_model = "beta"
    else:
        bayes_prob_treatment_better = _bayesian_normal_probability(control_vals, treatment_vals)
        bayesian_model = "normal"
    alpha = float(test.significance_level)
    significant = bool(p_val < alpha)
    winner = "inconclusive"
    if significant and relative_effect > 0:
        winner = "treatment"
    elif significant and relative_effect < 0:
        winner = "control"
    confidence = "high" if (significant and bayes_prob_treatment_better > 0.8) else "moderate"
    if not significant:
        confidence = "low"
    result = {
        "frequentist": {
            "t_statistic": float(t_stat),
            "p_value": float(p_val),
            "significant": significant,
        },
        "bayesian": {
            "prob_treatment_beats_control": float(bayes_prob_treatment_better),
            "model": bayesian_model,
        },
        "effect_size": {
            "relative_effect": float(relative_effect),
            "cohens_d": float(cohens_d),
        },
        "winner": winner,
        "confidence": confidence,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    test.results = result
    test.status = "completed"
    test.completed_at = datetime.now(timezone.utc)
    session.add(test)
    session.commit()
    metrics.AB_TESTS_COMPLETED_TOTAL.inc()
    emit_ab_lifecycle_event(session, test=test, status="completed")
    return result
