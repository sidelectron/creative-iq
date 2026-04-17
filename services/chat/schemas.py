"""Pydantic schemas for chat tools and APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatSendBody(BaseModel):
    content: str = Field(min_length=1)
    conversation_id: uuid.UUID | None = None


class ChatSendResponse(BaseModel):
    conversation_id: uuid.UUID
    response: str
    agent_type: str
    metadata: dict[str, Any]
    suggested_followups: list[str]


class ChatConversationItem(BaseModel):
    id: uuid.UUID
    title: str | None
    last_message_at: datetime | None
    message_count: int
    created_at: datetime


class ChatMessageItem(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    agent_type: str | None = None
    tool_calls: dict[str, Any] | None = None
    sources: dict[str, Any] | None = None
    created_at: datetime


class QueryBrandProfileInput(BaseModel):
    brand_id: uuid.UUID
    platform: str | None = None
    metric: str | None = None


class QueryAdPerformanceInput(BaseModel):
    brand_id: uuid.UUID
    platform: str | None = None
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class CompareAdsInput(BaseModel):
    ad_id_1: uuid.UUID
    ad_id_2: uuid.UUID


class SearchBrandMemoryInput(BaseModel):
    brand_id: uuid.UUID
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None


class AddBrandEventInput(BaseModel):
    brand_id: uuid.UUID
    event_type: str
    title: str
    description: str | None = None
    event_date: datetime
    impact_tags: list[str] = Field(default_factory=list)
    is_era_creating: bool | None = None


class UpdateUserPreferenceInput(BaseModel):
    user_id: uuid.UUID
    brand_id: uuid.UUID
    field: str
    value: Any


class DesignAbTestInput(BaseModel):
    brand_id: uuid.UUID
    attribute: str
    variants: list[str]
    metric: str


class GenerateCreativeBriefInput(BaseModel):
    brand_id: uuid.UUID
    campaign_description: str
    user_id: uuid.UUID | None = None
    platform: str | None = None
    num_variants: int = Field(default=3, ge=1, le=5)


class QuerySnowflakeInput(BaseModel):
    query_description: str
    row_limit: int = Field(default=1000, ge=1, le=1000)
