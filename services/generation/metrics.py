"""Prometheus metrics for Phase 7 generation (spec Step 11)."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

BRIEFS_GENERATED_TOTAL = Counter(
    "briefs_generated_total",
    "Total brief generation jobs completed.",
    labelnames=("brand_id", "platform"),
)

BRIEF_GENERATION_DURATION_SECONDS = Histogram(
    "brief_generation_duration_seconds",
    "Wall time from context_assembly start through output_assembly end.",
    buckets=(1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0, float("inf")),
)

BRIEF_COMPLIANCE_VIOLATIONS_TOTAL = Counter(
    "brief_compliance_violations_total",
    "Compliance violations detected.",
    labelnames=("severity",),
)

BRIEF_REVISION_LOOPS_TOTAL = Counter(
    "brief_revision_loops_total",
    "Primary brief revision loops executed after critical violations.",
)

BRIEF_VARIANTS_PER_REQUEST = Histogram(
    "brief_variants_per_request",
    "Number of variants produced per generation job.",
    buckets=(1, 2, 3, 4, 5, 6),
)

BRIEF_GEMINI_TOKENS_TOTAL = Counter(
    "brief_gemini_tokens_total",
    "Gemini tokens consumed by generation pipeline.",
    labelnames=("call_stage",),
)

BRIEF_FEEDBACK_TOTAL = Counter(
    "brief_feedback_total",
    "User feedback submissions on generated briefs.",
    labelnames=("rating",),
)
