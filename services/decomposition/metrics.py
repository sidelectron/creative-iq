"""Prometheus metrics for decomposition worker."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from shared.config.settings import settings

ADS_DECOMPOSED_TOTAL = Counter(
    "ads_decomposed_total",
    "Ads successfully decomposed",
    ["platform"],
)
ADS_DECOMPOSITION_FAILED_TOTAL = Counter(
    "ads_decomposition_failed_total",
    "Decomposition failures",
    ["failure_stage", "error_type"],
)
DECOMPOSITION_DURATION_SECONDS = Histogram(
    "decomposition_duration_seconds",
    "End-to-end decomposition duration",
    buckets=(5, 10, 20, 30, 45, 60, 90, 120, 180, 300, 360),
)
DECOMPOSITION_STAGE_DURATION_SECONDS = Histogram(
    "decomposition_stage_duration_seconds",
    "Per-stage duration",
    ["stage_name"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 90, 120),
)
GEMINI_API_CALLS_TOTAL = Counter(
    "gemini_api_calls_total",
    "Gemini API calls",
    ["model", "status"],
)
GEMINI_TOKENS_TOTAL = Counter(
    "gemini_tokens_total",
    "Gemini token usage",
    ["model", "direction"],
)
DECOMPOSITION_QUEUE_DEPTH = Gauge(
    "decomposition_queue_depth",
    "Approximate Redis list length for decomposition queue",
)


def start_metrics_server() -> None:
    start_http_server(settings.decomposition_metrics_port)
