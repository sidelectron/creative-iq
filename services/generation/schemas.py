"""Pydantic models for Phase 7 generation API and pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ToneEnum = Literal["formal", "casual", "playful", "professional"]


class LogoUsageRules(BaseModel):
    minimum_size: str | None = None
    clear_space: str | None = None
    placement_restrictions: str | None = None
    allowed_backgrounds: list[str] = Field(default_factory=list)


class ToneOfVoice(BaseModel):
    style: ToneEnum = "professional"
    description: str = ""


class StructuredGuidelinesBody(BaseModel):
    primary_colors: list[str] = Field(default_factory=list)
    secondary_colors: list[str] = Field(default_factory=list)
    font_primary: str | None = None
    font_secondary: str | None = None
    logo_usage: LogoUsageRules | None = None
    tone_of_voice: ToneOfVoice | None = None
    prohibited_content: list[str] = Field(default_factory=list)
    required_elements: list[str] = Field(default_factory=list)
    platform_rules: dict[str, str] = Field(default_factory=dict)


class GenerationCreateBody(BaseModel):
    campaign_description: str = Field(min_length=1, max_length=8000)
    platform: str | None = Field(default=None, max_length=32)
    target_audience: str | None = Field(default=None, max_length=4000)
    num_variants: int = Field(default=3, ge=1, le=5)
    include_scene_breakdown: bool = True
    parent_job_id: uuid.UUID | None = None
    variant_index: int | None = None
    user_adjustments: str | None = Field(default=None, max_length=8000)


class GenerationJobCreatedResponse(BaseModel):
    job_id: uuid.UUID


class GenerationFeedbackBody(BaseModel):
    variant_index: int = Field(ge=0, le=4)
    rating: int | str = Field(description="1-5 or thumbs_up / thumbs_down")
    feedback: str = Field(default="", max_length=8000)


def normalize_feedback_rating(rating: int | str) -> str:
    """Map API rating to Prometheus-safe label values."""
    if isinstance(rating, str):
        s = rating.strip().lower().replace(" ", "_")
        if s in ("thumbs_up", "up", "like"):
            return "thumbs_up"
        if s in ("thumbs_down", "down", "dislike"):
            return "thumbs_down"
    try:
        n = int(rating)
        if 1 <= n <= 5:
            return f"star_{n}"
    except (TypeError, ValueError):
        pass
    return "star_3"


class GenerationHistoryItem(BaseModel):
    id: uuid.UUID
    campaign_description: str
    num_variants: int
    created_at: datetime
    primary_summary: str
    chip_hook: str | None = None
    chip_duration: str | None = None
    chip_tone: str | None = None


class GenerationJobStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    pipeline_stage: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
