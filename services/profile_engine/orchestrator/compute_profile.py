"""Profile compute orchestrator for Phase 4."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from shared.config.settings import settings
from shared.utils.redis_sync import cache_setex_sync
from shared.utils.storage_sync import upload_bytes
from services.profile_engine import metrics
from services.profile_engine.scoring.categorical import score_categorical_rows
from services.profile_engine.scoring.cold_start import blend_profile_with_preset
from services.profile_engine.scoring.continuous import score_continuous_rows
from services.profile_engine.scoring.temporal import normalized_row_weights
from services.profile_engine.storage import repositories

log = structlog.get_logger()


def _as_builtin_categorical(scored: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for attr_name, values in scored.items():
        out[attr_name] = {k: v.__dict__ for k, v in values.items()}
    return out


def compute_brand_profile(session: Session, brand_id: uuid.UUID, platform: str) -> dict[str, Any]:
    """Compute and persist a brand profile for platform."""
    started = datetime.now(timezone.utc)
    with metrics.PROFILE_COMPUTATION_DURATION_SECONDS.time():
        brand = repositories.get_brand(session, brand_id)
        if brand is None:
            raise ValueError("Brand not found")

        cat_rows = repositories.snowflake_query(
            """
            SELECT *
            FROM MARTS.MART_BRAND_ATTRIBUTE_SCORES
            WHERE brand_id = %s AND platform = %s
            """,
            (str(brand_id), platform),
            query_type="mart_categorical",
        )
        cont_rows = repositories.snowflake_query(
            """
            SELECT *
            FROM MARTS.MART_CONTINUOUS_ATTRIBUTES
            WHERE brand_id = %s AND platform = %s
            """,
            (str(brand_id), platform),
            query_type="mart_continuous",
        )

        metric = str((brand.success_metrics or ["ctr"])[0]).lower()
        categorical_obj = score_categorical_rows(cat_rows, metric=metric)
        categorical = _as_builtin_categorical(categorical_obj)
        _apply_temporal_weighting(
            categorical,
            rows=repositories.get_temporal_rows(brand_id, platform, metric),
            eras=repositories.get_brand_eras(session, brand_id),
        )
        continuous = score_continuous_rows(cont_rows)

        preset = repositories.get_industry_preset(
            session, industry=brand.industry, platform=platform, audience_segment="all"
        )
        blended_categorical = blend_profile_with_preset(categorical, preset)

        all_conf: list[float] = []
        low_conf: list[str] = []
        for attr_name, values in blended_categorical.items():
            for value_name, payload in values.items():
                conf = float(payload.get("confidence", 0.0))
                all_conf.append(conf)
                if conf < 0.5:
                    low_conf.append(f"{attr_name}:{value_name}")

        overall_conf = sum(all_conf) / len(all_conf) if all_conf else 0.0
        total_ads = repositories.count_ads_for_brand(session, brand_id, platform)
        scoring_stage = "ml" if total_ads > 500 else "statistical"
        recommendations = _build_recommendations(blended_categorical, low_conf, metric)

        profile_data: dict[str, Any] = {
            "brand_id": str(brand_id),
            "platform": platform,
            "audience_segment": "all",
            "metric": metric,
            "scoring_stage": scoring_stage,
            "categorical": blended_categorical,
            "continuous": continuous,
            "overall_confidence": overall_conf,
            "total_ads_analyzed": total_ads,
            "low_confidence_attributes": low_conf,
            "recommendations": recommendations,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        key = f"{brand_id}/{platform}/statistical_profile.json"
        model_gcs_path = upload_bytes(
            settings.storage_bucket_models,
            key,
            repositories.dump_json(profile_data).encode("utf-8"),
            "application/json",
        )
        row = repositories.upsert_profile(
            session,
            brand_id=brand_id,
            platform=platform,
            profile_data=profile_data,
            overall_confidence=overall_conf,
            total_ads_analyzed=total_ads,
            model_gcs_path=model_gcs_path,
            scoring_stage=scoring_stage,
        )

        cache_setex_sync(
            f"brand_profile:{brand_id}:{platform}",
            3600,
            repositories.dump_json(profile_data),
        )
        staleness = (datetime.now(timezone.utc) - row.computed_at).total_seconds()
        metrics.PROFILE_STALENESS_SECONDS.labels(brand_id=str(brand_id), platform=platform).set(
            max(staleness, 0)
        )
        metrics.PROFILE_CONFIDENCE_MEAN.labels(brand_id=str(brand_id), platform=platform).set(
            overall_conf
        )
        metrics.PROFILE_COMPUTATIONS_TOTAL.labels(
            brand_id=str(brand_id), platform=platform, scoring_stage=scoring_stage
        ).inc()
        log.info(
            "profile_computed",
            brand_id=str(brand_id),
            platform=platform,
            metric=metric,
            confidence=overall_conf,
            elapsed_seconds=(datetime.now(timezone.utc) - started).total_seconds(),
        )
        repositories.insert_brand_event(
            session,
            brand_id=brand_id,
            event_type="profile_computed",
            title=f"Profile recomputed for {platform}",
            description="Profile computation completed.",
            source="auto_detected",
            metadata={"platform": platform, "overall_confidence": overall_conf},
        )
        return profile_data


def _build_recommendations(
    categorical: dict[str, dict[str, dict[str, Any]]],
    low_conf: list[str],
    metric: str,
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for attr_name, values in categorical.items():
        ordered = sorted(values.items(), key=lambda item: float(item[1].get("score", 0.0)), reverse=True)
        if not ordered:
            continue
        best_name, best_payload = ordered[0]
        recs.append(
            {
                "type": "keep_doing",
                "attribute": attr_name,
                "value": best_name,
                "message": f"{attr_name}={best_name} is top-performing for {metric}",
                "score": float(best_payload.get("score", 0.0)),
                "confidence": float(best_payload.get("confidence", 0.0)),
                "sample_size": int(best_payload.get("sample_size", 0)),
            }
        )
        scores = [float(v.get("score", 0.0)) for v in values.values()]
        confs = [float(v.get("confidence", 0.0)) for v in values.values()]
        if scores:
            variance_impact = max(scores) - min(scores)
            avg_conf = (sum(confs) / len(confs)) if confs else 0.0
            impact_priority = variance_impact * (1.0 - avg_conf)
            if avg_conf < 0.7:
                candidates.append(
                    {
                        "type": "ab_test_candidate",
                        "attribute": attr_name,
                        "impact_priority": impact_priority,
                        "variance_impact": variance_impact,
                        "confidence": avg_conf,
                        "message": f"High variance but low confidence for {attr_name}; run A/B test.",
                    }
                )
    candidates.sort(key=lambda c: float(c["impact_priority"]), reverse=True)
    recs.extend(candidates[:3])
    return recs[:10]


def _apply_temporal_weighting(
    categorical: dict[str, dict[str, dict[str, Any]]],
    *,
    rows: list[dict[str, Any]],
    eras: list[dict[str, Any]],
) -> None:
    """Adjust categorical scores using temporally weighted per-ad evidence."""
    if not rows:
        return
    weights = normalized_row_weights(rows, eras)
    value_weighted_sum: dict[str, dict[str, float]] = {}
    value_weight_total: dict[str, dict[str, float]] = {}
    for row, weight in zip(rows, weights, strict=False):
        metric_value = row.get("metric_value")
        if metric_value is None:
            continue
        for attr_name in ("hook_type", "narrative_arc", "emotional_tone", "cta_type", "visual_style"):
            value = row.get(attr_name)
            if value is None:
                continue
            a = value_weighted_sum.setdefault(attr_name, {})
            b = value_weight_total.setdefault(attr_name, {})
            key = str(value)
            a[key] = a.get(key, 0.0) + (float(metric_value) * float(weight))
            b[key] = b.get(key, 0.0) + float(weight)

    for attr_name, values in categorical.items():
        weighted_scores = value_weighted_sum.get(attr_name, {})
        weighted_totals = value_weight_total.get(attr_name, {})
        if not weighted_scores:
            continue
        for value_name, payload in values.items():
            total_w = weighted_totals.get(value_name, 0.0)
            if total_w <= 0:
                continue
            temporal_score = weighted_scores[value_name] / total_w
            base_score = float(payload.get("score", 1.0))
            payload["score"] = (0.5 * base_score) + (0.5 * temporal_score)
