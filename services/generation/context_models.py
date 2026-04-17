"""Typed context for generation (Phase 7 Step 3) — single Pydantic envelope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerationContext(BaseModel):
    """Structured context passed to brief / compliance / variants (serializable dict via model_dump)."""

    brand_id: str
    brand_name: str = ""
    industry: str | None = None
    platform: str = "meta"
    campaign_description: str = ""
    profile_raw: dict[str, Any] = Field(default_factory=dict)
    profile_top_attributes: list[dict[str, Any]] = Field(default_factory=list)
    audience_signals: dict[str, Any] = Field(default_factory=dict)
    current_era: dict[str, Any] | None = None
    timeline_last_5: list[dict[str, Any]] = Field(default_factory=list)
    user_preferences: dict[str, Any] | None = None
    guidelines_structured: dict[str, Any] = Field(default_factory=dict)
    guidelines_document_summary: dict[str, Any] = Field(
        default_factory=lambda: {"summary": "", "key_rules": []}
    )
    reference_ads: list[dict[str, Any]] = Field(default_factory=list)
    active_ab_tests: list[dict[str, Any]] = Field(default_factory=list)
    assembly_ms: int = 0
    user_adjustments: str | None = None

    def as_prompt_dict(self) -> dict[str, Any]:
        """JSON-friendly dict for Gemini prompts (legacy call sites expect dict)."""
        return self.model_dump(mode="json")
