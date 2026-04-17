"""Primary structured brief generation (Phase 7 Step 4)."""

from __future__ import annotations

import json
from typing import Any

from shared.config.settings import settings
from shared.utils.gemini import GeminiError, generate_json


def _build_prompt(
    ctx: dict[str, Any],
    *,
    include_scene_breakdown: bool,
    revision_notes: str | None,
) -> str:
    scenes = (
        "Include scene_breakdown: list of scenes with duration_seconds, visual_description, "
        "text_overlay, audio_cue, attributes_expressed[]."
        if include_scene_breakdown
        else "Set scene_breakdown to empty array []."
    )
    rev = revision_notes or ""
    user_adj = str(ctx.get("user_adjustments") or "").strip()
    if user_adj:
        rev = (rev + "\n\nUser iteration requests (honor without inventing new data):\n" + user_adj).strip()
    return (
        "You are a creative strategist. Using ONLY the JSON context below, produce a structured "
        "creative brief as JSON with keys: campaign_overview (string 2-3 sentences), "
        "target_audience (string), attribute_specs (array of objects with keys: name, recommended, "
        "reasoning_with_data_citation, confidence high|medium|low, data_backing object with score and "
        "sample_size, alternative optional if confidence not high), "
        f"{scenes} "
        "what_to_avoid (string[] with data citations), confidence_summary (object high|medium|low string[]). "
        "Attribute names should cover: hook_type, narrative_arc, emotional_tone, duration_seconds, "
        "pacing, color_direction, cta_strategy, audio_direction, text_overlays, product_appearance, "
        "human_presence, logo.\n"
        f"Revision instructions from compliance (may be empty): {rev}\n"
        f"CONTEXT_JSON:\n{json.dumps(ctx, default=str)[:100_000]}"
    )


def generate_primary_brief(
    ctx: dict[str, Any],
    *,
    include_scene_breakdown: bool,
    revision_notes: str | None = None,
) -> tuple[dict[str, Any], int, int]:
    """Return (brief_dict, input_tokens, output_tokens)."""
    prompt = _build_prompt(ctx, include_scene_breakdown=include_scene_breakdown, revision_notes=revision_notes)
    data, inp, out = generate_json(
        model=settings.gemini_model_pro,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config={"temperature": 0.7},
        cache_key_parts={"gen_brief": ctx.get("brand_id"), "camp": ctx.get("campaign_description", "")[:200]},
    )
    return dict(data), inp, out
