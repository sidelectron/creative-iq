from datetime import datetime, timedelta, timezone

from services.profile_engine.scoring.categorical import score_categorical_rows
from services.profile_engine.scoring.cold_start import blend_attribute_score
from services.profile_engine.scoring.continuous import score_continuous_rows
from services.profile_engine.scoring.temporal import normalized_row_weights


def test_categorical_scoring_assigns_rank_and_confidence() -> None:
    rows = [
        {
            "attribute_name": "hook_type",
            "attribute_value": "testimonial",
            "sample_size": 120,
            "performance_index_ctr": 1.4,
            "stddev_metric_value": 0.2,
        },
        {
            "attribute_name": "hook_type",
            "attribute_value": "product_first",
            "sample_size": 80,
            "performance_index_ctr": 0.9,
            "stddev_metric_value": 0.25,
        },
    ]
    out = score_categorical_rows(rows, metric="ctr")
    assert out["hook_type"]["testimonial"].rank == 1
    assert out["hook_type"]["product_first"].rank == 2
    assert out["hook_type"]["testimonial"].confidence > 0


def test_continuous_scoring_detects_optimal_range() -> None:
    rows = [
        {"attribute_name": "duration_seconds", "correlation": 0.03, "p_value": 0.11, "bin_lower": 0, "bin_upper": 5, "performance_score": 0.9, "sample_size": 30},
        {"attribute_name": "duration_seconds", "correlation": 0.03, "p_value": 0.11, "bin_lower": 5, "bin_upper": 10, "performance_score": 1.25, "sample_size": 35},
        {"attribute_name": "duration_seconds", "correlation": 0.03, "p_value": 0.11, "bin_lower": 10, "bin_upper": 15, "performance_score": 0.88, "sample_size": 20},
    ]
    out = score_continuous_rows(rows)
    assert out["duration_seconds"]["optimal_range"] == (5.0, 10.0)
    assert out["duration_seconds"]["is_non_linear"] is True


def test_temporal_weighting_prioritizes_recent_ads() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        {"published_at": now - timedelta(days=7)},
        {"published_at": now - timedelta(days=365)},
    ]
    weights = normalized_row_weights(rows, eras=[], now=now)
    assert weights[0] > weights[1]
    assert abs(sum(weights) - 1.0) < 1e-6


def test_cold_start_blending_switches_dominance() -> None:
    effective, dominance = blend_attribute_score(1.4, 1.1, 0.2)
    assert dominance == "preset_dominated"
    assert effective > 1.1
