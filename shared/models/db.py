"""SQLAlchemy ORM models (PostgreSQL + pgvector)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from uuid_utils.compat import uuid7


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    brand_memberships: Mapped[list[BrandMember]] = relationship(
        "BrandMember", back_populates="user", cascade="all, delete-orphan"
    )


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    guidelines_gcs_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    success_metrics: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[\"ctr\"]'::jsonb")
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    members: Mapped[list[BrandMember]] = relationship(
        "BrandMember", back_populates="brand", cascade="all, delete-orphan"
    )
    ads: Mapped[list[Ad]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    events: Mapped[list[BrandEvent]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    eras: Mapped[list[BrandEra]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    profiles: Mapped[list[BrandProfile]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )


class BrandMember(Base):
    __tablename__ = "brand_members"
    __table_args__ = (UniqueConstraint("brand_id", "user_id", name="uq_brand_member_brand_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped[Brand] = relationship("Brand", back_populates="members")
    user: Mapped[User] = relationship("User", back_populates="brand_memberships")


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (
        Index("ix_ads_brand_id", "brand_id"),
        Index("ix_ads_platform", "platform"),
        Index("ix_ads_status", "status"),
        Index("ix_ads_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    ad_format: Mapped[str] = mapped_column(String(32), default="video", nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gcs_video_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_gcs_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ingested", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ad_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    brand: Mapped[Brand] = relationship(back_populates="ads")
    performance_rows: Mapped[list[AdPerformance]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    fingerprint: Mapped[CreativeFingerprint | None] = relationship(
        back_populates="ad", uselist=False, cascade="all, delete-orphan"
    )


class AdPerformance(Base):
    __tablename__ = "ad_performance"
    __table_args__ = (
        UniqueConstraint("ad_id", "date", name="uq_ad_performance_ad_date"),
        Index("ix_ad_performance_ad_id", "ad_id"),
        Index("ix_ad_performance_date", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    ad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    video_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    video_completions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    engagement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    perf_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )

    ad: Mapped[Ad] = relationship(back_populates="performance_rows")

    @property
    def ctr(self) -> float | None:
        if self.impressions <= 0:
            return None
        return self.clicks / self.impressions

    @property
    def cpa(self) -> float | None:
        if self.conversions <= 0:
            return None
        return float(self.spend) / self.conversions

    @property
    def roas(self) -> float | None:
        if self.spend <= 0:
            return None
        return float(self.revenue) / float(self.spend)

    @property
    def completion_rate(self) -> float | None:
        if self.video_views <= 0:
            return None
        return self.video_completions / self.video_views


class CreativeFingerprint(Base):
    __tablename__ = "creative_fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    ad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ads.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    low_level_features: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    gemini_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    gemini_model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gemini_tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gemini_tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ad: Mapped[Ad] = relationship(back_populates="fingerprint")


class BrandEvent(Base):
    __tablename__ = "brand_events"
    __table_args__ = (
        Index("ix_brand_events_brand_id", "brand_id"),
        Index("ix_brand_events_event_date", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    impact_tags: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped[Brand] = relationship("Brand", back_populates="events")


class BrandEra(Base):
    __tablename__ = "brand_eras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    era_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggering_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brand_events.id"), nullable=True
    )
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped[Brand] = relationship(back_populates="eras")


class BrandProfile(Base):
    __tablename__ = "brand_profiles"
    __table_args__ = (
        UniqueConstraint(
            "brand_id", "platform", "audience_segment", name="uq_brand_profile_brand_platform_audience"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    audience_segment: Mapped[str] = mapped_column(String(128), default="all", nullable=False)
    scoring_stage: Mapped[str] = mapped_column(String(32), default="statistical", nullable=False)
    profile_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    overall_confidence: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_ads_analyzed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_gcs_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped[Brand] = relationship(back_populates="profiles")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_id", "conversation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sources: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ABTest(Base):
    __tablename__ = "ab_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    attribute_tested: Mapped[str] = mapped_column(String(255), nullable=False)
    variants: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    target_metric: Mapped[str] = mapped_column(String(64), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_size_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    significance_level: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.05"), nullable=False
    )
    power: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.80"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserBrandPreference(Base):
    __tablename__ = "user_brand_preferences"
    __table_args__ = (UniqueConstraint("user_id", "brand_id", name="uq_user_brand_pref_user_brand"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    success_metrics: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    creative_preferences: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    strategic_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SyncState(Base):
    """Track per-table PostgreSQL -> Snowflake incremental sync watermarks."""

    __tablename__ = "sync_state"
    __table_args__ = (UniqueConstraint("table_name", name="uq_sync_state_table_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GenerationJob(Base):
    """Async creative brief generation job (Phase 7)."""

    __tablename__ = "generation_jobs"
    __table_args__ = (
        Index("ix_generation_jobs_brand_id", "brand_id"),
        Index("ix_generation_jobs_brand_created", "brand_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    pipeline_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped[Brand] = relationship(back_populates="generation_jobs")


class IndustryPreset(Base):
    __tablename__ = "industry_presets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    industry: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    audience_segment: Mapped[str] = mapped_column(String(128), default="all", nullable=False)
    baseline_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
