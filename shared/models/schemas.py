"""Pydantic v2 schemas for API requests and responses."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from shared.models.enums import (
    BrandRole,
    Platform,
)

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int


# --- User / Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Brand ---
class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry: str | None = None
    description: str | None = None
    website_url: str | None = None
    success_metrics: list[str] | None = None


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = None
    description: str | None = None
    website_url: str | None = None
    success_metrics: list[str] | None = None
    settings: dict[str, Any] | None = None


class BrandMemberInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    full_name: str
    role: BrandRole


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: str | None
    description: str | None
    website_url: str | None
    guidelines_gcs_path: str | None
    success_metrics: list[Any]
    settings: dict[str, Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    member_count: int = 0
    members: list[BrandMemberInfo] = Field(default_factory=list)


class BrandListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: str | None
    created_at: datetime
    role: BrandRole


class BrandMemberCreate(BaseModel):
    email: EmailStr
    role: BrandRole


class BrandMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    full_name: str
    role: BrandRole


# --- Ad ---
class AdUploadMeta(BaseModel):
    """Metadata accompanying multipart upload (validated after form parse)."""

    platform: Platform
    title: str | None = None
    description: str | None = None
    published_at: datetime | None = None


class AdPerformanceSummary(BaseModel):
    total_impressions: int = 0
    total_clicks: int = 0
    average_ctr: float | None = None


class AdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    external_id: str | None
    platform: str
    ad_format: str
    title: str | None
    description: str | None
    gcs_video_path: str | None
    thumbnail_gcs_path: str | None
    duration_seconds: float | None
    resolution: str | None
    source: str
    status: str
    published_at: datetime | None
    deactivated_at: datetime | None
    run_duration_days: int | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    signed_video_url: str | None = None
    performance_summary: AdPerformanceSummary | None = None
    error_message: str | None = None
    fingerprint_attributes: dict[str, Any] | None = None


class CreativeFingerprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ad_id: uuid.UUID
    attributes: dict[str, Any]
    low_level_features: dict[str, Any] | None
    gemini_analysis: dict[str, Any] | None
    transcript: str | None
    gemini_model_used: str | None = None
    gemini_tokens_input: int | None = None
    gemini_tokens_output: int | None = None
    processing_duration_seconds: float | None = None
    created_at: datetime


class AdDecompositionStatusResponse(BaseModel):
    status: str
    progress: dict[str, Any] | None = None


class AdCompareResponse(BaseModel):
    ads: list[dict[str, Any]]
    differences: dict[str, Any]


class BatchDecomposeBody(BaseModel):
    ad_ids: Union[list[uuid.UUID], Literal["all"]]


class BatchDecomposeResponse(BaseModel):
    queued_count: int
    ad_ids: list[uuid.UUID]


class AdDetailResponse(AdResponse):
    performances: list["AdPerformanceResponse"] = Field(default_factory=list)
    fingerprint: CreativeFingerprintResponse | None = None


# --- Phase 4 Profile / AB ---
class ProfileComputeResponse(BaseModel):
    status: str
    profile: dict[str, Any]


class ProfileResponse(BaseModel):
    profile: dict[str, Any]
    highlights: list[dict[str, Any]]
    data_health: dict[str, Any]


class ProfileAttributeResponse(BaseModel):
    attribute_name: str
    values: dict[str, Any]
    trend: list[dict[str, Any]]
    recommended_value: str


class ProfileRecommendationsResponse(BaseModel):
    recommendations: list[dict[str, Any]]


class ABTestCreateBody(BaseModel):
    attribute_to_test: str
    variants: list[str] = Field(min_length=2)
    target_metric: str
    hypothesis: str | None = None
    baseline_metric: float | None = None
    avg_cpm: float | None = None
    avg_daily_impressions: float | None = None


class ABTestDesignPreviewResponse(BaseModel):
    """Non-persisted output of `design_test` for wizard review UI."""

    sample_size_per_variant: int
    estimated_budget_per_variant: float | None
    estimated_duration_days: int | None
    hypothesis: str
    alpha: float
    power: float
    mde_relative: float
    mde_absolute: float


class ABTestStatusPatchBody(BaseModel):
    status: Literal["active", "completed", "cancelled"]
    platform: str = "meta"


class ABTestAssignAdsBody(BaseModel):
    assignments: dict[str, list[uuid.UUID]]


class ABTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    created_by: uuid.UUID
    attribute_tested: str
    variants: list[Any]
    target_metric: str
    hypothesis: str | None
    sample_size_required: int | None
    estimated_budget: Decimal | None
    estimated_duration_days: int | None
    significance_level: Decimal
    power: Decimal
    status: str
    results: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class DriftAlertResponse(BaseModel):
    event_id: uuid.UUID
    event_date: datetime
    attribute_key: str
    historical_score: float
    recent_score: float
    direction: str
    magnitude_relative: float
    recent_sample_size: int


# --- Phase 5 Brand Memory ---
class EventCreateBody(BaseModel):
    event_type: Literal[
        "product_launch",
        "positioning_shift",
        "agency_change",
        "competitor_action",
        "user_note",
    ]
    title: str = Field(min_length=1, max_length=512)
    event_date: datetime
    description: str | None = None
    impact_tags: list[str] = Field(default_factory=list)
    is_era_creating: bool | None = None


class EventUpdateBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    event_date: datetime | None = None
    description: str | None = None
    impact_tags: list[str] | None = None
    is_era_creating: bool | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    event_type: str
    title: str
    description: str | None
    source: str
    event_date: datetime
    impact_tags: list[Any]
    metadata: dict[str, Any]
    created_at: datetime


class EventSearchBody(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    start_date: datetime | None = None
    end_date: datetime | None = None


class EventSearchResult(BaseModel):
    event_id: uuid.UUID
    event_type: str
    title: str
    description: str | None
    event_date: datetime
    source: str
    similarity: float
    era: dict[str, Any] | None
    metadata: dict[str, Any]


class EraResponse(BaseModel):
    id: uuid.UUID
    era_name: str
    start_date: datetime
    end_date: datetime | None
    triggering_event_id: uuid.UUID | None
    context_summary: str | None
    ads_count: int
    average_performance: dict[str, float]


class TimelineResponseItem(BaseModel):
    timestamp: datetime
    event_type: str
    title: str
    description: str | None
    source: str
    impact: dict[str, Any]
    related_data: dict[str, Any]


class EventImpactRequest(BaseModel):
    force_recompute: bool = False
    pre_days: int = Field(default=30, ge=7, le=180)
    post_days: int = Field(default=30, ge=7, le=180)


class EventImpactResponse(BaseModel):
    event_id: uuid.UUID
    summary: str
    pre_window: dict[str, Any]
    post_window: dict[str, Any]
    deltas: dict[str, float]
    significance: dict[str, Any]
    cached: bool = False


class PresetResponse(BaseModel):
    industry: str
    platform: str
    audience_segment: str
    baseline_profile: dict[str, Any]
    description: str | None


# --- Phase 6 Chat ---
class ChatSendBody(BaseModel):
    content: str = Field(min_length=1)
    conversation_id: uuid.UUID | None = None


class ChatSendResponse(BaseModel):
    conversation_id: uuid.UUID
    response: str
    agent_type: str
    metadata: dict[str, Any]
    suggested_followups: list[str]


class ChatConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    last_message_at: datetime | None
    message_count: int
    created_at: datetime


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    agent_type: str | None = None
    tool_calls: dict[str, Any] | None = None
    sources: dict[str, Any] | None = None
    created_at: datetime


# --- Performance ---
class AdPerformanceCreate(BaseModel):
    date: date
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    conversions: int = Field(ge=0)
    spend: Decimal = Field(ge=Decimal("0"))
    revenue: Decimal = Field(ge=Decimal("0"))
    video_views: int = Field(ge=0)
    video_completions: int = Field(ge=0)
    engagement_count: int = Field(ge=0)
    metadata: dict[str, Any] | None = None


class AdPerformanceBulkCreate(BaseModel):
    records: list[AdPerformanceCreate]


class AdPerformanceBulkResult(BaseModel):
    count: int


class AdPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ad_id: uuid.UUID
    date: date
    impressions: int
    clicks: int
    conversions: int
    spend: Decimal
    revenue: Decimal
    video_views: int
    video_completions: int
    engagement_count: int
    metadata: dict[str, Any]
    ctr: float | None = None
    cpa: float | None = None
    roas: float | None = None
    completion_rate: float | None = None


def ad_performance_response_from_model(perf: Any) -> AdPerformanceResponse:
    """Build performance API model from SQLAlchemy row (handles `perf_metadata` column)."""
    return AdPerformanceResponse(
        id=perf.id,
        ad_id=perf.ad_id,
        date=perf.date,
        impressions=perf.impressions,
        clicks=perf.clicks,
        conversions=perf.conversions,
        spend=perf.spend,
        revenue=perf.revenue,
        video_views=perf.video_views,
        video_completions=perf.video_completions,
        engagement_count=perf.engagement_count,
        metadata=perf.perf_metadata,
        ctr=perf.ctr,
        cpa=perf.cpa,
        roas=perf.roas,
        completion_rate=perf.completion_rate,
    )


def ad_response_from_model(
    ad: Any,
    *,
    signed_video_url: str | None = None,
    performance_summary: AdPerformanceSummary | None = None,
    fingerprint_attributes: dict[str, Any] | None = None,
) -> AdResponse:
    """Build ad API model from SQLAlchemy row."""
    return AdResponse(
        id=ad.id,
        brand_id=ad.brand_id,
        external_id=ad.external_id,
        platform=ad.platform,
        ad_format=ad.ad_format,
        title=ad.title,
        description=ad.description,
        gcs_video_path=ad.gcs_video_path,
        thumbnail_gcs_path=ad.thumbnail_gcs_path,
        duration_seconds=ad.duration_seconds,
        resolution=ad.resolution,
        source=ad.source,
        status=ad.status,
        published_at=ad.published_at,
        deactivated_at=ad.deactivated_at,
        run_duration_days=ad.run_duration_days,
        metadata=ad.ad_metadata,
        created_at=ad.created_at,
        updated_at=ad.updated_at,
        deleted_at=ad.deleted_at,
        signed_video_url=signed_video_url,
        performance_summary=performance_summary,
        error_message=(ad.ad_metadata or {}).get("error")
        if getattr(ad, "status", None) == "failed"
        else None,
        fingerprint_attributes=fingerprint_attributes,
    )
