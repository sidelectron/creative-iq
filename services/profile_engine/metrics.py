"""Prometheus metrics for profile engine and A/B workflows."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from shared.config.settings import settings

PROFILE_COMPUTATIONS_TOTAL = Counter(
    "profile_computations_total",
    "Total profile computations",
    ["brand_id", "platform", "scoring_stage"],
)
PROFILE_COMPUTATION_DURATION_SECONDS = Histogram(
    "profile_computation_duration_seconds",
    "Profile computation duration in seconds",
)
PROFILE_STALENESS_SECONDS = Gauge(
    "profile_staleness_seconds",
    "Profile staleness in seconds",
    ["brand_id", "platform"],
)
PROFILE_CONFIDENCE_MEAN = Gauge(
    "profile_confidence_mean",
    "Average profile confidence",
    ["brand_id", "platform"],
)
SNOWFLAKE_QUERY_DURATION_SECONDS = Histogram(
    "snowflake_query_duration_seconds",
    "Snowflake query duration in seconds",
    ["query_type"],
)
AB_TESTS_DESIGNED_TOTAL = Counter("ab_tests_designed_total", "Total A/B tests designed")
AB_TESTS_COMPLETED_TOTAL = Counter("ab_tests_completed_total", "Total A/B tests completed")
DRIFT_ALERTS_TOTAL = Counter(
    "drift_alerts_total", "Total drift alerts emitted", ["attribute_name"]
)

_METRICS_STARTED = False


def start_metrics_server() -> None:
    """Start Prometheus metrics server once for profile engine workers."""
    global _METRICS_STARTED
    if _METRICS_STARTED:
        return
    start_http_server(settings.profile_engine_metrics_port)
    _METRICS_STARTED = True
